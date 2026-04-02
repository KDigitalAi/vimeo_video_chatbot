"""
Chat tracking persistence and dispatch helpers.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from functools import lru_cache

from app.application.ports.tracking_port import TrackingPort
from app.core.request_context import get_request_context
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe
from app.services.conversation_turn_store import store_chat_interaction

logger = get_logger_safe(__name__)


def _expected_query_embedding_dims() -> int:
    """Must match DB `vector(1536)` and OpenAI `text-embedding-3-small` output."""
    try:
        return int(getattr(get_settings_safe(), "EMBEDDING_DIMENSIONS", 1536))
    except (TypeError, ValueError):
        return 1536


def _format_vector_for_pgvector(query_embedding: list | None) -> str | None:
    """Serialize full embedding for PostgREST; DB expects same dimension as pdf_embeddings."""
    if not query_embedding:
        return None
    expected = _expected_query_embedding_dims()
    actual = len(query_embedding)
    if actual != expected:
        logger.warning(
            "Query embedding dimension mismatch; not storing vector (expected DB-compatible length)",
            component="chat_tracking",
            operation="store_user_query",
            embedding_dim=actual,
            expected_dim=expected,
        )
        return None
    return "[" + ",".join(str(float(x)) for x in query_embedding) + "]"


def _persist_chat_tracking_sync(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
    tracking_task_id: str,
):
    """Persist chat history and user query tracking without affecting the response path."""
    tracking_ok = True
    try:
        logger.info(
            "Persisting chat history",
            component="chat_tracking",
            operation="persist_chatbot_turn",
            tracking_task_id=tracking_task_id,
            user_id=user_id,
            session_id=session_id,
        )
        chat_id = store_chat_interaction(
            user_id=user_id,
            session_id=session_id,
            user_message=query_text,
            bot_response=answer,
        )
        if chat_id:
            logger.info(
                "Chat history persisted",
                component="chat_tracking",
                operation="persist_chatbot_turn",
                tracking_task_id=tracking_task_id,
                user_id=user_id,
                session_id=session_id,
                chat_id=chat_id,
                result="success",
            )
        else:
            logger.warning(
                "Chat history persistence returned no id",
                component="chat_tracking",
                operation="persist_chatbot_turn",
                tracking_task_id=tracking_task_id,
                user_id=user_id,
                session_id=session_id,
                result="empty",
            )
            tracking_ok = False

        try:
            from app.database.supabase import get_supabase

            supabase = get_supabase()
            matched_chunk_id = (
                str(sources[0].get("chunk_id"))
                if sources and sources[0].get("chunk_id") is not None
                else None
            )
            logger.info(
                "Persisting user query",
                component="chat_tracking",
                operation="store_user_query",
                tracking_task_id=tracking_task_id,
                user_id=user_id,
                session_id=session_id,
                has_matched_chunk=matched_chunk_id is not None,
            )
            logger.info(
                "Using table: chatbot_user_queries",
                component="chat_tracking",
                operation="store_user_query",
                tracking_task_id=tracking_task_id,
                user_id=user_id,
                session_id=session_id,
            )
            query_embedding_str = _format_vector_for_pgvector(
                list(query_embedding) if query_embedding is not None else None
            )
            if query_embedding_str:
                logger.debug(
                    "query_embedding ready for persistence",
                    component="chat_tracking",
                    operation="store_user_query",
                    embedding_dim=len(query_embedding) if query_embedding else 0,
                    expected_dim=_expected_query_embedding_dims(),
                )
            query_record = {
                "user_id": user_id,
                "query_text": query_text,
                "query_embedding": query_embedding_str,
                "matched_chunk_id": matched_chunk_id,
            }
            result = supabase.table("chatbot_user_queries").insert(query_record).execute()
            if result.data:
                logger.info(
                    "User query persisted",
                    component="chat_tracking",
                    operation="store_user_query",
                    tracking_task_id=tracking_task_id,
                    user_id=user_id,
                    session_id=session_id,
                    query_id=result.data[0].get("id"),
                    result="success",
                )
            else:
                logger.warning(
                    "User query persistence returned no data",
                    component="chat_tracking",
                    operation="store_user_query",
                    tracking_task_id=tracking_task_id,
                    user_id=user_id,
                    session_id=session_id,
                    result="empty",
                )
                tracking_ok = False
        except Exception as e:
            logger.exception(
                "User query persistence failed",
                component="chat_tracking",
                operation="store_user_query",
                tracking_task_id=tracking_task_id,
                user_id=user_id,
                session_id=session_id,
            )
            tracking_ok = False
    except Exception as e:
        logger.exception(
            "Conversation turn persistence failed",
            component="chat_tracking",
            operation="persist_chatbot_turn",
            tracking_task_id=tracking_task_id,
            user_id=user_id,
            session_id=session_id,
        )
        tracking_ok = False
    return tracking_ok


async def _persist_chat_tracking_async(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
    tracking_task_id: str,
):
    """Run blocking persistence work in a background thread."""
    persisted = await asyncio.to_thread(
        _persist_chat_tracking_sync,
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
        tracking_task_id=tracking_task_id,
    )
    if not persisted:
        raise RuntimeError("Background chat tracking did not complete successfully")


async def _safe_persist_chat_tracking(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
    max_retries: int = 3,
    tracking_task_id: str,
):
    """Persist tracking with retry, without affecting the response path."""
    start_time = time.perf_counter()
    kwargs = dict(
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
        tracking_task_id=tracking_task_id,
    )
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Background tracking attempt started",
                component="chat_tracking",
                operation="tracking_attempt",
                tracking_task_id=tracking_task_id,
                attempt=attempt,
                max_retries=max_retries,
                user_id=user_id,
                session_id=session_id,
            )
            await _persist_chat_tracking_async(**kwargs)
            logger.info(
                "Background tracking completed",
                component="chat_tracking",
                operation="tracking_complete",
                tracking_task_id=tracking_task_id,
                attempt=attempt,
                user_id=user_id,
                session_id=session_id,
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                result="success",
            )
            return
        except Exception as e:
            logger.exception(
                "Background tracking attempt failed",
                component="chat_tracking",
                operation="tracking_attempt",
                tracking_task_id=tracking_task_id,
                attempt=attempt,
                max_retries=max_retries,
                user_id=user_id,
                session_id=session_id,
            )
            if attempt < max_retries:
                await asyncio.sleep(min(0.25 * attempt, 1.0))
            else:
                logger.error(
                    "Background tracking failed permanently",
                    component="chat_tracking",
                    operation="tracking_complete",
                    tracking_task_id=tracking_task_id,
                    attempt=attempt,
                    max_retries=max_retries,
                    user_id=user_id,
                    session_id=session_id,
                    duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                    result="failure",
                )


async def _dispatch_chat_tracking(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
):
    """Defer persistence in production, but complete it inline during tests."""
    tracking_task_id = str(uuid.uuid4())
    request_context = get_request_context()
    kwargs = dict(
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
        tracking_task_id=tracking_task_id,
    )
    logger.info(
        "Background tracking dispatched",
        component="chat_tracking",
        operation="tracking_dispatch",
        tracking_task_id=tracking_task_id,
        user_id=user_id,
        session_id=session_id,
        request_id=request_context.get("request_id"),
    )
    if os.getenv("PYTEST_CURRENT_TEST"):
        await _safe_persist_chat_tracking(**kwargs)
    else:
        asyncio.create_task(_safe_persist_chat_tracking(**kwargs))


async def dispatch_tracking(*, request, session_id, answer, query_embedding, sources):
    """Thin wrapper to keep route orchestration readable."""
    await _dispatch_chat_tracking(
        user_id=request.user_id or "anonymous",
        session_id=session_id,
        query_text=request.query,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
    )


class BackgroundTrackingService(TrackingPort):
    """Tracking port adapter backed by async background persistence."""

    async def track_chat(
        self,
        *,
        user_id: str,
        session_id: str,
        query_text: str,
        answer: str,
        query_embedding,
        sources: list,
    ) -> None:
        await _dispatch_chat_tracking(
            user_id=user_id,
            session_id=session_id,
            query_text=query_text,
            answer=answer,
            query_embedding=query_embedding,
            sources=sources,
        )


@lru_cache(maxsize=1)
def get_tracking_service() -> TrackingPort:
    """Return the cached tracking port implementation."""
    return BackgroundTrackingService()

