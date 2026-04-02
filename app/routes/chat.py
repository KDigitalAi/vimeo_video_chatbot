"""Thin HTTP routes for chatbot endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Query

from app.application.chat.dependencies import get_chat_query_service
from app.application.chat.session_service import (
    clear_conversation_memory as clear_conversation_memory_service,
    clear_user_conversation_turns as clear_user_conversation_turns_service,
    create_new_session as create_new_session_service,
    delete_user_chat_session as delete_user_chat_session_service,
    end_session as end_session_service,
    get_session_conversation_turns as get_session_conversation_turns_service,
    get_user_chat_sessions as get_user_chat_sessions_service,
)
from app.services.adapters.session_memory import get_session_service
from app.models.schemas import ChatQueryPayload, ChatResponse, SessionEndRequest

router = APIRouter(
    tags=["chat"],
    responses={
        200: {"description": "Successful response"},
    },
)
session_service = get_session_service()

CANONICAL_CHAT_API_NOTE = "Prefer `/chat/sessions`, `/chat/sessions/{session_id}`, and related resource routes."
LEGACY_CHAT_API_NOTE = (
    "Deprecated legacy alias kept for backward compatibility. "
    "Prefer the resource-oriented routes documented under `/chat/*`."
)


def _end_session_by_id(session_id: str):
    """Forward a session-id based delete request to the shared session service."""
    return end_session_service(session_service, {"session_id": session_id})


async def _forward_to_canonical(handler, *args, **kwargs):
    """Forward a legacy alias to its canonical handler."""
    return await handler(*args, **kwargs)


@router.post(
    "/queries",
    response_model=ChatResponse,
    summary="Create chat query (schema-hidden)",
    description=(
        "Same handler as `POST /chat/query`; omitted from OpenAPI to avoid duplicate documentation."
    ),
    include_in_schema=False,
)
async def create_chat_query(request_data: ChatQueryPayload = Body(...)):
    """Submit a chat query and receive a grounded answer with optional sources."""
    return await get_chat_query_service().handle_chat_query(request_data.request)


@router.post(
    "/sessions",
    summary="Create chat session",
    description="Create a new server-managed chat session. This canonical endpoint does not require a request body.",
)
async def create_chat_session():
    """Create a new chat session resource."""
    return create_new_session_service(session_service)


@router.delete(
    "/sessions/{session_id}",
    summary="Delete chat session",
    description="End a chat session resource by session id.",
)
async def delete_chat_session_resource(session_id: str):
    """End an existing chat session."""
    return _end_session_by_id(session_id)


@router.delete(
    "/sessions/{session_id}/memory",
    summary="Clear chat session memory",
    description=(
        "Clear the in-memory conversation state for a session without deleting stored history. "
        "Omitted from OpenAPI; prefer this path over legacy `/chat/clear-memory/{session_id}`."
    ),
    include_in_schema=False,
)
async def delete_chat_session_memory(session_id: str):
    """Clear in-memory conversation state for a chat session."""
    return clear_conversation_memory_service(session_service, session_id)


@router.get(
    "/sessions/{session_id}/history",
    summary="Get session history",
    description="Retrieve persisted chat history for a specific session resource.",
)
async def get_chat_session_history(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=100),
):
    """Return chat history for a session."""
    return get_session_conversation_turns_service(session_id, limit)


@router.get(
    "/users/{user_id}/sessions",
    summary="List user sessions",
    description=(
        "List chat session resources associated with a user identifier. "
        "Omitted from OpenAPI to keep the documented contract minimal; endpoint remains supported."
    ),
    include_in_schema=False,
)
async def get_user_session_collection(user_id: str):
    """List chat sessions for a user."""
    return get_user_chat_sessions_service(user_id)


@router.delete(
    "/users/{user_id}/sessions/{session_id}",
    summary="Delete user session",
    description=(
        "Delete a specific chat session belonging to a user. "
        "Omitted from OpenAPI; use `DELETE /chat/sessions/{session_id}` when you have the session id."
    ),
    include_in_schema=False,
)
async def delete_user_chat_session_resource(user_id: str, session_id: str):
    """Delete one user-owned chat session."""
    return delete_user_chat_session_service(user_id, session_id)


@router.delete(
    "/users/{user_id}/history",
    summary="Delete user history",
    description=(
        "Delete all persisted chat history for a user and clear in-memory session state. "
        "Omitted from OpenAPI to keep the documented surface small; endpoint remains supported."
    ),
    include_in_schema=False,
)
async def delete_user_persisted_turns_resource(user_id: str):
    """Delete all persisted conversation turns for a user."""
    return clear_user_conversation_turns_service(session_service, user_id)


# Public contract + backward-compatible aliases (aliases hidden from OpenAPI)
@router.post(
    "/query",
    response_model=ChatResponse,
    summary="Submit chat query",
    description=(
        "Submit a chat query against the PDF-backed knowledge base and receive a grounded answer with optional sources."
    ),
)
async def query_chat(request_data: ChatQueryPayload = Body(...)):
    """Backward-compatible alias for creating a chat query."""
    return await _forward_to_canonical(create_chat_query, request_data)


@router.post(
    "/session/create",
    summary="Legacy alias: create chat session",
    description=(
        "Legacy alias for `POST /chat/sessions`. "
        "Request body is accepted for backward compatibility but ignored. "
        f"{LEGACY_CHAT_API_NOTE}"
    ),
    include_in_schema=False,
)
async def create_new_session(request_data: dict = Body(...)):
    """Backward-compatible alias for session creation."""
    return await _forward_to_canonical(create_chat_session)


@router.post(
    "/session/end",
    summary="Legacy alias: end chat session",
    description=f"Legacy alias for `DELETE /chat/sessions/{{session_id}}`. {LEGACY_CHAT_API_NOTE}",
    include_in_schema=False,
)
async def end_session(request_data: SessionEndRequest = Body(...)):
    """Backward-compatible alias for session deletion."""
    return _end_session_by_id(request_data.session_id)


@router.get(
    "/history/{session_id}",
    summary="Legacy alias: get session history",
    description=f"Legacy alias for `GET /chat/sessions/{{session_id}}/history`. {LEGACY_CHAT_API_NOTE}",
)
async def get_session_conversation_turns_alias(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=100),
):
    """Backward-compatible alias for session history retrieval."""
    return await _forward_to_canonical(get_chat_session_history, session_id, limit)


@router.get(
    "/sessions/{user_id}",
    summary="Legacy alias: list user sessions",
    description=f"Legacy alias for `GET /chat/users/{{user_id}}/sessions`. {LEGACY_CHAT_API_NOTE}",
    include_in_schema=False,
)
async def get_user_chat_sessions(user_id: str):
    """Backward-compatible alias for listing user sessions."""
    return await _forward_to_canonical(get_user_session_collection, user_id)


@router.delete(
    "/session/{user_id}/{session_id}",
    summary="Legacy alias: delete user session",
    description=f"Legacy alias for `DELETE /chat/users/{{user_id}}/sessions/{{session_id}}`. {LEGACY_CHAT_API_NOTE}",
)
async def delete_user_chat_session(user_id: str, session_id: str):
    """Backward-compatible alias for deleting one user session."""
    return await _forward_to_canonical(delete_user_chat_session_resource, user_id, session_id)


@router.post(
    "/clear-memory/{session_id}",
    summary="Legacy alias: clear session memory",
    description=f"Legacy alias for `DELETE /chat/sessions/{{session_id}}/memory`. {LEGACY_CHAT_API_NOTE}",
    include_in_schema=False,
)
async def clear_conversation_memory(session_id: str):
    """Backward-compatible alias for clearing session memory."""
    return await _forward_to_canonical(delete_chat_session_memory, session_id)


@router.delete(
    "/history/{user_id}",
    summary="Legacy alias: delete user history",
    description=f"Legacy alias for `DELETE /chat/users/{{user_id}}/history`. {LEGACY_CHAT_API_NOTE}",
    include_in_schema=False,
)
async def clear_user_conversation_turns_alias(user_id: str):
    """Backward-compatible alias for deleting all user history."""
    return await _forward_to_canonical(delete_user_persisted_turns_resource, user_id)



