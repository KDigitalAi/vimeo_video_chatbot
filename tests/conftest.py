from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.app_factory import create_app
from app.models.schemas import ChatResponse


@dataclass
class DummyDoc:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class StubChatService:
    def __init__(self, response: ChatResponse | None = None, side_effect: Exception | None = None):
        self.response = response or ChatResponse(
            answer="Python is a programming language.",
            sources=[
                {
                    "source_type": "pdf",
                    "pdf_title": "Python Basics",
                    "pdf_id": "pdf-1",
                    "page_number": 1,
                    "chunk_id": 1,
                    "relevance_score": 0.91,
                    "source_name": "Python Basics",
                }
            ],
            conversation_id="session-123",
            processing_time=0.123,
            tokens_used=None,
        )
        self.side_effect = side_effect
        self.handle_chat_query = AsyncMock(side_effect=self._handle)

    async def _handle(self, request):
        if self.side_effect:
            raise self.side_effect
        return self.response


class StubSessionService:
    def __init__(self):
        self.ensure_active_session_calls: list[str | None] = []
        self.get_or_create_session_calls: list[str] = []
        self.append_messages_calls: list[tuple[str, str, str]] = []
        self.clear_session_calls: list[str] = []
        self.clear_all_sessions_called = False
        self.messages_by_session: dict[str, list[dict[str, str]]] = {}

    def ensure_active_session(self, session_id: str | None) -> str:
        self.ensure_active_session_calls.append(session_id)
        return session_id or "generated-session"

    def get_or_create_session(self, session_id: str):
        self.get_or_create_session_calls.append(session_id)
        return {"session_id": session_id}

    def get_recent_messages(self, session_id: str) -> list[dict[str, str]]:
        return self.messages_by_session.get(session_id, [])

    def append_messages(self, session_id: str, user_message: str, assistant_message: str) -> None:
        self.append_messages_calls.append((session_id, user_message, assistant_message))

    def clear_session(self, session_id: str) -> None:
        self.clear_session_calls.append(session_id)

    def clear_all_sessions(self) -> None:
        self.clear_all_sessions_called = True


class StubEmbeddings:
    def __init__(self, vector: list[float] | None = None, side_effect: Exception | None = None):
        self.vector = vector or [0.1, 0.2, 0.3]
        self.side_effect = side_effect
        self.calls: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.side_effect:
            raise self.side_effect
        return self.vector


class StubRetrievalPort:
    def __init__(self, docs_with_scores: list[tuple[Any, float]] | None = None, side_effect: Exception | None = None):
        self.docs_with_scores = docs_with_scores or []
        self.side_effect = side_effect
        self.calls: list[tuple[list[float], int]] = []

    def retrieve(self, query_embedding: list[float], k: int) -> list[tuple[Any, float]]:
        self.calls.append((query_embedding, k))
        if self.side_effect:
            raise self.side_effect
        return list(self.docs_with_scores)


class StubGenerationService:
    def __init__(self, answer: str = "Grounded answer", side_effect: Exception | None = None):
        self.answer = answer
        self.side_effect = side_effect
        self.calls: list[dict[str, Any]] = []

    def generate_answer(self, **kwargs) -> str:
        self.calls.append(kwargs)
        if self.side_effect:
            raise self.side_effect
        return self.answer


class StubTrackingService:
    def __init__(self):
        self.track_chat = AsyncMock()


@pytest.fixture(autouse=True)
def clear_caches():
    from app.application.chat import dependencies
    from app.services.vector_store import get_retrieval_service

    dependencies.get_chat_query_service.cache_clear()
    get_retrieval_service.cache_clear()
    yield
    dependencies.get_chat_query_service.cache_clear()
    get_retrieval_service.cache_clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)

