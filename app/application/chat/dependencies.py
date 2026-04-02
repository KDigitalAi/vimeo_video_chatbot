"""Dependency wiring for chat application services."""
from __future__ import annotations

from functools import lru_cache

from app.application.chat.query_service import ChatQueryService
from app.application.chat.response_builder import ChatResponseBuilder
from app.application.chat.retrieval_service import ChatRetrievalService
from app.application.chat.session_service import ChatSessionService
from app.services.adapters.session_memory import get_session_service
from app.services.adapters.tracking_background import get_tracking_service
from app.services.adapters.embeddings_openai import get_embeddings_service
from app.services.adapters.retrieval_supabase import get_retrieval_service
from app.services.generation.grounded_generation import get_generation_service


@lru_cache(maxsize=1)
def get_chat_query_service() -> ChatQueryService:
    session_port = get_session_service()
    return ChatQueryService(
        embeddings=get_embeddings_service(),
        retrieval_service=ChatRetrievalService(get_retrieval_service()),
        session_service=ChatSessionService(session_port),
        response_builder=ChatResponseBuilder(get_generation_service()),
        tracking=get_tracking_service(),
    )
