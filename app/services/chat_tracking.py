"""
Chat tracking persistence and dispatch helpers.
"""
from __future__ import annotations

import asyncio
import os

from app.utils.runtime_helpers import get_logger_safe
from app.services.chat_history_manager import store_chat_interaction

logger = get_logger_safe(__name__)


def _persist_chat_tracking_sync(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
):
    """Persist chat history and user query tracking without affecting the response path."""
    tracking_ok = True
    try:
        logger.info("Inserting chat history into chatbot_chat_history")
        chat_id = store_chat_interaction(
            user_id=user_id,
            session_id=session_id,
            user_message=query_text,
            bot_response=answer,
        )
        if chat_id:
            logger.info("Chat interaction stored in chatbot_chat_history with ID: %s", chat_id)
        else:
            logger.warning(
                "Failed to store chat interaction in chatbot_chat_history (store_chat_interaction returned None)"
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
                "Inserting query into chatbot_user_queries%s",
                " with matched_chunk_id" if matched_chunk_id is not None else "",
            )
            query_embedding_str = (
                "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
                if query_embedding
                else None
            )
            query_record = {
                "user_id": user_id,
                "query_text": query_text,
                "query_embedding": query_embedding_str,
                "matched_chunk_id": matched_chunk_id,
            }
            result = supabase.table("chatbot_user_queries").insert(query_record).execute()
            if result.data:
                logger.info("User query stored in chatbot_user_queries with ID: %s", result.data[0].get("id"))
            else:
                logger.warning("Failed to store user query in chatbot_user_queries - insert returned no data")
                tracking_ok = False
        except Exception as e:
            logger.error("Error inserting user query in chatbot_user_queries: %s", e, exc_info=True)
            tracking_ok = False
    except Exception as e:
        logger.error("Error storing chat interaction in chatbot_chat_history: %s", e, exc_info=True)
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
):
    """Persist tracking with retry, without affecting the response path."""
    kwargs = dict(
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
    )
    for attempt in range(1, max_retries + 1):
        try:
            await _persist_chat_tracking_async(**kwargs)
            return
        except Exception as e:
            logger.error(
                "Tracking failed on attempt %d/%d for session %s: %s",
                attempt,
                max_retries,
                session_id,
                e,
                exc_info=True,
            )
            if attempt < max_retries:
                await asyncio.sleep(min(0.25 * attempt, 1.0))


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
    kwargs = dict(
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
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

