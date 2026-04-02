"""Thin chat query orchestration service."""
from __future__ import annotations

import asyncio
import random
import time

from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError

from app.application.chat.policies import (
    GREETING_RESPONSES,
    apply_gating_policy,
    is_greeting,
)
from app.application.chat.response_builder import ChatResponseBuilder
from app.application.chat.retrieval_service import ChatRetrievalService
from app.application.chat.session_service import ChatSessionService
from app.application.ports.embeddings_port import EmbeddingsPort
from app.application.ports.tracking_port import TrackingPort
from app.core.request_context import enrich_request_context
from app.models.schemas import ChatRequest
from app.core.exceptions import DependencyError, ValidationError
from app.utils.runtime_helpers import get_logger_safe

logger = get_logger_safe(__name__)


class ChatQueryService:
    def __init__(
        self,
        *,
        embeddings: EmbeddingsPort,
        retrieval_service: ChatRetrievalService,
        session_service: ChatSessionService,
        response_builder: ChatResponseBuilder,
        tracking: TrackingPort,
    ):
        self._embeddings = embeddings
        self._retrieval_service = retrieval_service
        self._session_service = session_service
        self._response_builder = response_builder
        self._tracking = tracking

    async def _build_request_context(self, request: ChatRequest) -> tuple[ChatRequest, str, str]:
        """Normalize identity and session context."""
        user_id = request.user_id or "anonymous"
        session_id = await asyncio.to_thread(
            self._session_service.ensure_active_session,
            request.conversation_id,
        )
        request.conversation_id = session_id
        enrich_request_context(user_id=user_id, session_id=session_id)
        logger.info(
            "Chat request context prepared",
            component="chat_query_service",
            operation="prepare_request_context",
            user_id=user_id,
            session_id=session_id,
            top_k=request.top_k,
        )
        return request, user_id, session_id

    async def _handle_greeting(self, *, request: ChatRequest, user_id: str, session_id: str):
        """Return the greeting response flow."""
        answer = random.choice(GREETING_RESPONSES)
        await self._tracking.track_chat(
            user_id=user_id,
            session_id=session_id,
            query_text=request.query,
            answer=answer,
            query_embedding=None,
            sources=[],
        )
        return self._response_builder.build_response(
            answer=answer,
            sources=[],
            session_id=session_id,
            processing_time=0.1,
        )

    async def _process_query(self, *, request: ChatRequest, session_id: str) -> tuple[str, list, list | None, bool]:
        """Run the main retrieval and generation flow."""
        answer = "I'm sorry, but I encountered an error processing your query. Please try again."
        sources = []
        query_embedding = None

        embedding_start = time.perf_counter()
        query_context = await asyncio.to_thread(
            self._session_service.build_query_context,
            session_id=session_id,
            query=request.query,
        )
        query_embedding = await asyncio.to_thread(
            self._embeddings.embed_query,
            query_context.search_query,
        )
        embedding_time_ms = round((time.perf_counter() - embedding_start) * 1000, 2)
        logger.info(
            "Embedding generated",
            component="chat_query_service",
            operation="generate_embedding",
            session_id=session_id,
            embedding_time_ms=embedding_time_ms,
            is_follow_up=query_context.is_follow_up,
        )

        retrieval_start = time.perf_counter()
        retrieval_result = await asyncio.to_thread(
            self._retrieval_service.retrieve,
            query_embedding=query_embedding,
            top_k=request.top_k,
        )
        retrieval_time_ms = round((time.perf_counter() - retrieval_start) * 1000, 2)
        logger.info(
            "Retrieval completed",
            component="chat_query_service",
            operation="retrieve_documents",
            session_id=session_id,
            retrieval_time_ms=retrieval_time_ms,
            docs_with_scores=len(retrieval_result.docs_with_scores),
            retrieval_best=retrieval_result.retrieval_best,
            avg_top3_score=retrieval_result.quality.avg_top3_score,
            num_chunks=retrieval_result.quality.num_chunks,
            degraded_fallback=retrieval_result.retrieval_used_degraded_fallback,
        )
        gating_decision = apply_gating_policy(
            request.query,
            retrieval_result.docs_with_scores,
            retrieval_result.quality,
            retrieval_result.thresholds,
        )

        if gating_decision.should_refuse:
            answer = gating_decision.answer or answer
            sources = gating_decision.sources or []
            logger.info(
                "Gating refused response generation",
                component="chat_query_service",
                operation="apply_gating_policy",
                session_id=session_id,
                source_count=len(sources),
                result_type="refused",
                reason=gating_decision.reason,
                degraded_fallback=retrieval_result.retrieval_used_degraded_fallback,
            )
            return answer, sources, query_embedding, retrieval_result.retrieval_used_degraded_fallback

        generation_start = time.perf_counter()
        conversation_session = await asyncio.to_thread(
            self._session_service.ensure_conversation_session,
            session_id,
            query_context.conversation_session,
        )
        answer = await asyncio.to_thread(
            self._response_builder.generate_answer,
            request=request,
            relevant_docs=gating_decision.relevant_docs,
            thresholds=retrieval_result.thresholds,
            retrieval_best=retrieval_result.retrieval_best or 0.0,
            conversation_session=conversation_session,
            is_follow_up=query_context.is_follow_up,
        )
        await asyncio.to_thread(
            self._session_service.append_turn,
            session_id,
            request.query,
            answer,
        )
        sources = await asyncio.to_thread(
            self._response_builder.build_sources,
            request=request,
            relevant_docs=gating_decision.relevant_docs,
            thresholds=retrieval_result.thresholds,
            answer=answer,
        )
        generation_time_ms = round((time.perf_counter() - generation_start) * 1000, 2)
        logger.info(
            "Response generated",
            component="chat_query_service",
            operation="generate_response",
            session_id=session_id,
            generation_time_ms=generation_time_ms,
            source_count=len(sources),
            answer_mode=gating_decision.mode,
        )
        return answer, sources, query_embedding, retrieval_result.retrieval_used_degraded_fallback

    async def _track_and_build_response(
        self,
        *,
        request: ChatRequest,
        user_id: str,
        session_id: str,
        answer: str,
        sources: list,
        query_embedding,
        start_time: float,
        degraded_fallback: bool,
    ):
        """Persist tracking and build the final response."""
        processing_time = round(time.time() - start_time, 3)
        await self._tracking.track_chat(
            user_id=user_id,
            session_id=session_id,
            query_text=request.query,
            answer=answer,
            query_embedding=query_embedding,
            sources=sources,
        )
        logger.info(
            "Tracking dispatched",
            component="chat_query_service",
            operation="dispatch_tracking",
            user_id=user_id,
            session_id=session_id,
            processing_time=processing_time,
            source_count=len(sources),
        )
        logger.info(
            "Chat request summary",
            component="chat_query_service",
            operation="chat_request_summary",
            user_id=user_id,
            session_id=session_id,
            result_type="refused" if not sources and answer.startswith("Sorry") else "answered",
            source_count=len(sources),
            degraded_fallback=degraded_fallback,
            total_duration_ms=round(processing_time * 1000, 2),
        )
        return self._response_builder.build_response(
            answer=answer,
            sources=sources,
            session_id=session_id,
            processing_time=processing_time,
        )

    async def handle_chat_query(self, request: ChatRequest):
        """Handle the full chat query lifecycle."""
        start_time = time.time()
        logger.info(
            "Chat request received",
            component="chat_query_service",
            operation="receive_request",
            query_length=len(request.query),
        )
        request, user_id, session_id = await self._build_request_context(request)

        if is_greeting(request.query):
            return await self._handle_greeting(
                request=request,
                user_id=user_id,
                session_id=session_id,
            )

        try:
            answer, sources, query_embedding, degraded_fallback = await self._process_query(
                request=request,
                session_id=session_id,
            )
        except (ValidationError, PydanticValidationError):
            raise HTTPException(status_code=422, detail="Request validation failed")
        except DependencyError:
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Chat query processing failed",
                component="chat_query_service",
                operation="handle_chat_query",
                session_id=session_id,
            )
            logger.error(
                "Chat request summary",
                component="chat_query_service",
                operation="chat_request_summary",
                user_id=user_id,
                session_id=session_id,
                result_type="error",
                source_count=0,
                degraded_fallback=False,
                total_duration_ms=round((time.time() - start_time) * 1000, 2),
            )
            raise HTTPException(status_code=500, detail="Internal server error") from exc

        return await self._track_and_build_response(
            request=request,
            user_id=user_id,
            session_id=session_id,
            answer=answer,
            sources=sources,
            query_embedding=query_embedding,
            start_time=start_time,
            degraded_fallback=degraded_fallback,
        )
