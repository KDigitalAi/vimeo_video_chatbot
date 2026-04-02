from __future__ import annotations

from fastapi import APIRouter

from app.core.app_factory import create_app
from app.core.exceptions import DependencyError


def test_request_id_header_exists(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers


def test_root_returns_backend_json(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/json")
    assert response.json() == {"message": "Backend is running"}


def test_validation_error_envelope(client):
    response = client.post("/chat/queries", json={"request": {"query": ""}})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation_error"
    assert payload["message"] == "Request validation failed"
    assert payload["path"] == "/chat/queries"
    assert payload["method"] == "POST"


def test_http_exception_envelope_from_route(client, monkeypatch):
    import app.routes.chat as chat_routes
    from tests.conftest import StubChatService

    monkeypatch.setattr(
        chat_routes,
        "get_chat_query_service",
        lambda: StubChatService(side_effect=DependencyError("dependency down")),
    )

    response = client.post("/chat/queries", json={"request": {"query": "What is Python?"}})

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "dependency_unavailable"
    assert payload["message"] == "dependency down"


def test_global_http_exception_handler_returns_standardized_envelope():
    app = create_app()
    router = APIRouter()

    @router.get("/boom-http")
    async def boom_http():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Unavailable")

    app.include_router(router)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/boom-http")

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "http_error"
    assert payload["message"] == "Unavailable"


def test_global_app_error_handler_returns_standardized_envelope():
    app = create_app()
    router = APIRouter()

    @router.get("/boom-app")
    async def boom_app():
        raise DependencyError("Service temporarily unavailable")

    app.include_router(router)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/boom-app")

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "dependency_unavailable"
    assert payload["message"] == "Service temporarily unavailable"

