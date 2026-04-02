from __future__ import annotations

from fastapi import HTTPException

from app.core.exceptions import DependencyError
from app.models.schemas import ChatResponse
from tests.conftest import StubChatService


def test_post_chat_queries_happy_path(client, monkeypatch):
    import app.routes.chat as chat_routes

    service = StubChatService(
        response=ChatResponse(
            answer="Python is a programming language.",
            sources=[
                {
                    "source_type": "pdf",
                    "pdf_title": "Python Basics",
                    "pdf_id": "pdf-1",
                    "page_number": 2,
                    "chunk_id": 7,
                    "relevance_score": 0.88,
                    "source_name": "Python Basics",
                }
            ],
            conversation_id="session-abc",
            processing_time=0.321,
            tokens_used=None,
        )
    )
    monkeypatch.setattr(chat_routes, "get_chat_query_service", lambda: service)

    response = client.post(
        "/chat/queries",
        json={"request": {"query": "What is Python?", "user_id": "user-1"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Python is a programming language."
    assert payload["conversation_id"] == "session-abc"
    assert payload["sources"][0]["pdf_id"] == "pdf-1"
    assert "X-Request-ID" in response.headers
    assert service.handle_chat_query.await_count == 1


def test_post_chat_queries_greeting_short_circuit(client, monkeypatch):
    import app.routes.chat as chat_routes

    service = StubChatService(
        response=ChatResponse(
            answer="Hello! I'm your Learning Assistant. How can I help you with your study materials today?",
            sources=[],
            conversation_id="greeting-session",
            processing_time=0.1,
            tokens_used=None,
        )
    )
    monkeypatch.setattr(chat_routes, "get_chat_query_service", lambda: service)

    response = client.post("/chat/queries", json={"request": {"query": "hi"}})

    assert response.status_code == 200
    assert "Learning Assistant" in response.json()["answer"]
    assert response.json()["sources"] == []
    assert service.handle_chat_query.await_count == 1


def test_post_chat_queries_refusal_path(client, monkeypatch):
    import app.routes.chat as chat_routes

    service = StubChatService(
        response=ChatResponse(
            answer="Sorry, I can only answer questions related to the available PDF study materials.",
            sources=[],
            conversation_id="session-refusal",
            processing_time=0.11,
            tokens_used=None,
        )
    )
    monkeypatch.setattr(chat_routes, "get_chat_query_service", lambda: service)

    response = client.post("/chat/queries", json={"request": {"query": "What is Java?"}})

    assert response.status_code == 200
    assert response.json()["answer"].startswith("Sorry")
    assert response.json()["sources"] == []


def test_post_chat_queries_dependency_failure_returns_standard_error(client, monkeypatch):
    import app.routes.chat as chat_routes

    service = StubChatService(side_effect=HTTPException(status_code=503, detail="Service temporarily unavailable"))
    monkeypatch.setattr(chat_routes, "get_chat_query_service", lambda: service)

    response = client.post("/chat/queries", json={"request": {"query": "What is Python?"}})

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "http_error"
    assert payload["message"] == "Service temporarily unavailable"
    assert payload["path"] == "/chat/queries"
    assert payload["method"] == "POST"


def test_post_chat_queries_validation_error_returns_422(client):
    response = client.post("/chat/queries", json={"request": {"query": ""}})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation_error"
    assert payload["message"] == "Request validation failed"
    assert payload["path"] == "/chat/queries"


def test_legacy_and_canonical_chat_query_routes_match(client, monkeypatch):
    import app.routes.chat as chat_routes

    service = StubChatService()
    monkeypatch.setattr(chat_routes, "get_chat_query_service", lambda: service)

    body = {"request": {"query": "What is Python?", "user_id": "user-1"}}
    canonical = client.post("/chat/queries", json=body)
    legacy = client.post("/chat/query", json=body)

    assert canonical.status_code == 200
    assert legacy.status_code == 200
    assert canonical.json() == legacy.json()


def test_legacy_and_canonical_session_routes_match(client, monkeypatch):
    import app.routes.chat as chat_routes

    monkeypatch.setattr(
        chat_routes,
        "create_new_session_service",
        lambda session_service: {
            "session_id": "session-1",
            "created_at": "2026-01-01T00:00:00Z",
            "message": "New session created successfully",
        },
    )

    canonical = client.post("/chat/sessions")
    legacy = client.post("/chat/session/create", json={"ignored": True})

    assert canonical.status_code == 200
    assert legacy.status_code == 200
    assert canonical.json() == legacy.json()

