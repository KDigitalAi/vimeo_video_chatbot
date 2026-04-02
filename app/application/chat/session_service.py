"""Application chat session orchestration."""
from __future__ import annotations

from dataclasses import dataclass
import time

from fastapi import HTTPException, status
from app.application.chat.policies import is_follow_up_query
from app.application.ports.session_port import SessionPort
from app.core.exceptions import NotFoundError, ValidationError
from app.services.persistence.conversation_turn_persistence import (
    clear_all_conversation_turns_for_user,
    delete_chat_session,
    list_conversation_turns_for_session,
    get_chat_sessions,
)
from app.services.persistence.user_profile_store import deactivate_session_by_id
from app.utils.runtime_helpers import get_logger_safe

logger = get_logger_safe(__name__)


@dataclass
class QuerySessionContext:
    session_id: str
    search_query: str
    is_follow_up: bool
    conversation_session: object | None


class ChatSessionService:
    def __init__(self, session_port: SessionPort):
        self._session_port = session_port

    def ensure_active_session(self, session_id: str | None) -> str:
        return self._session_port.ensure_active_session(session_id)

    def build_query_context(self, *, session_id: str, query: str) -> QuerySessionContext:
        is_follow_up = is_follow_up_query(query)
        search_query = query
        conversation_session = None

        if is_follow_up:
            conversation_session = self._session_port.get_or_create_session(session_id)
            messages = self._session_port.get_recent_messages(session_id)
            last_user_message = None
            last_assistant_message = None
            for message in reversed(messages):
                if message["role"] == "assistant" and last_assistant_message is None:
                    last_assistant_message = message["content"]
                elif message["role"] == "user" and last_user_message is None:
                    last_user_message = message["content"]
                    break
            if last_user_message and last_assistant_message:
                search_query = f"{last_user_message} | {query}"

        return QuerySessionContext(
            session_id=session_id,
            search_query=search_query,
            is_follow_up=is_follow_up,
            conversation_session=conversation_session,
        )

    def ensure_conversation_session(self, session_id: str, conversation_session: object | None):
        return conversation_session or self._session_port.get_or_create_session(session_id)

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        self._session_port.append_messages(session_id, user_message, assistant_message)


def _validate_session_id(session_id: str | None, *, field_name: str = "session_id") -> str:
    """Normalize and validate a session id used by route-facing helpers."""
    if not session_id or not str(session_id).strip():
        detail = f"{field_name} must not be empty" if field_name != "session_id" else "session_id must not be empty"
        raise ValidationError(detail)
    return str(session_id).strip()


def _validate_user_id(user_id: str | None) -> str:
    """Normalize and validate a user id used by route-facing helpers."""
    if not user_id or not str(user_id).strip():
        raise ValidationError("user_id must not be empty")
    return str(user_id).strip()


def _validate_limit(limit: int) -> int:
    """Validate history pagination limits."""
    if limit < 1 or limit > 100:
        raise ValidationError("limit must be between 1 and 100")
    return limit


def create_new_session(session_port: SessionPort) -> dict:
    new_session_id = session_port.ensure_active_session(None)
    if not new_session_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session",
        )
    logger.info(
        "Session created",
        component="chat_session_service",
        session_id=new_session_id,
    )
    return {
        "session_id": new_session_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": "New session created successfully",
    }


def end_session(session_port: SessionPort, request_data: dict) -> dict:
    if "session_id" not in request_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required field: session_id")
    session_id = _validate_session_id(request_data.get("session_id"))
    deactivate_session_by_id(session_id)
    session_port.clear_session(session_id)
    logger.info(
        "Session ended",
        component="chat_session_service",
        session_id=session_id,
    )
    return {
        "message": "Session ended successfully",
        "session_id": session_id,
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def get_session_conversation_turns(session_id: str, limit: int = 50) -> dict:
    session_id = _validate_session_id(session_id)
    limit = _validate_limit(limit)
    history = list_conversation_turns_for_session(session_id, limit)
    logger.info(
        "Session history retrieved",
        component="chat_session_service",
        session_id=session_id,
        limit=limit,
        history_count=len(history),
    )
    return {
        "session_id": session_id,
        "history": history,
        "count": len(history),
        "message": "Only data from this session is returned",
    }


def get_user_chat_sessions(user_id: str) -> dict:
    user_id = _validate_user_id(user_id)
    sessions = get_chat_sessions(user_id)
    logger.info(
        "User sessions retrieved",
        component="chat_session_service",
        user_id=user_id,
        session_count=len(sessions),
    )
    return {"user_id": user_id, "sessions": sessions, "count": len(sessions)}


def delete_user_chat_session(user_id: str, session_id: str) -> dict:
    user_id = _validate_user_id(user_id)
    session_id = _validate_session_id(session_id)
    delete_chat_session(user_id, session_id)
    logger.info(
        "User session deleted",
        component="chat_session_service",
        user_id=user_id,
        session_id=session_id,
    )
    return {"message": f"Chat session {session_id} deleted successfully"}


def clear_conversation_memory(session_port: SessionPort, session_id: str) -> dict:
    session_id = _validate_session_id(session_id)
    session_port.clear_session(session_id)
    logger.info(
        "Conversation memory cleared",
        component="chat_session_service",
        session_id=session_id,
    )
    return {"message": f"Conversation memory cleared for session {session_id}"}


def clear_user_conversation_turns(session_port: SessionPort, user_id: str) -> dict:
    user_id = _validate_user_id(user_id)
    clear_all_conversation_turns_for_user(user_id)
    session_port.clear_all_sessions()
    logger.info(
        "User chat history cleared",
        component="chat_session_service",
        user_id=user_id,
    )
    return {
        "message": f"All chat history and conversation memory for user {user_id} cleared successfully"
    }
