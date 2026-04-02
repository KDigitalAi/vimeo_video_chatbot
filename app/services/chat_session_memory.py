"""
In-memory chat session memory and lifecycle helpers.
"""
from __future__ import annotations

import time
import uuid
from functools import lru_cache

from app.application.ports.session_port import SessionPort
from app.core.exceptions import DependencyError, NotFoundError
from app.services.user_profile_manager import is_session_active, set_active_session_by_session_id

# In-memory session storage limits to prevent unbounded growth.
MAX_IN_MEMORY_SESSIONS = 100
MAX_SESSION_MESSAGES = 20
SESSION_TTL_SECONDS = 60 * 60
SESSION_VALIDATION_TTL_SECONDS = 120

# Global dictionary to store conversation chains per session
_conversation_chains = {}
_session_validation_cache: dict[str, tuple[float, bool]] = {}


class _HumanMemoryMessage:
    def __init__(self, content: str):
        self.content = content


class _AIMemoryMessage:
    def __init__(self, content: str):
        self.content = content


class _SimpleChatMemory:
    def __init__(self):
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append(_HumanMemoryMessage(content))
        self._trim_messages()

    def add_ai_message(self, content: str):
        self.messages.append(_AIMemoryMessage(content))
        self._trim_messages()

    def _trim_messages(self):
        if len(self.messages) > MAX_SESSION_MESSAGES:
            self.messages = self.messages[-MAX_SESSION_MESSAGES:]


class _SimpleConversationMemory:
    def __init__(self):
        self.chat_memory = _SimpleChatMemory()


class _SimpleConversationSession:
    def __init__(self):
        self.memory = _SimpleConversationMemory()
        self.created_at = time.time()
        self.last_accessed_at = self.created_at

    def touch(self):
        self.last_accessed_at = time.time()


def _expire_stale_conversation_chains(now: float | None = None):
    """Drop sessions that have been inactive longer than the configured TTL."""
    now = now if now is not None else time.time()
    expired_session_ids = [
        session_id
        for session_id, session in _conversation_chains.items()
        if now - getattr(session, "last_accessed_at", now) > SESSION_TTL_SECONDS
    ]
    for session_id in expired_session_ids:
        del _conversation_chains[session_id]


def _enforce_conversation_chain_limit():
    """Evict the oldest in-memory sessions when the session cap is exceeded."""
    while len(_conversation_chains) > MAX_IN_MEMORY_SESSIONS:
        oldest_session_id = min(
            _conversation_chains,
            key=lambda sid: getattr(_conversation_chains[sid], "last_accessed_at", 0),
        )
        del _conversation_chains[oldest_session_id]


def _get_or_create_conversation_chain(session_id: str, vector_store):
    """Get or create lightweight session memory for the given session."""
    _expire_stale_conversation_chains()
    if session_id not in _conversation_chains:
        _conversation_chains[session_id] = _SimpleConversationSession()
        _enforce_conversation_chain_limit()
    session = _conversation_chains[session_id]
    session.touch()
    return session


def _clear_conversation_chain(session_id: str):
    """Clear conversation chain for a session (when chat is cleared)."""
    if session_id in _conversation_chains:
        del _conversation_chains[session_id]
    _session_validation_cache.pop(session_id, None)


def _get_cached_session_active(session_id: str) -> bool | None:
    """Return cached session activity when still fresh."""
    cached = _session_validation_cache.get(session_id)
    if not cached:
        return None
    expires_at, is_active = cached
    if expires_at < time.time():
        _session_validation_cache.pop(session_id, None)
        return None
    return is_active


def _set_cached_session_active(session_id: str, is_active: bool) -> None:
    """Cache session activity for a short TTL."""
    _session_validation_cache[session_id] = (
        time.time() + SESSION_VALIDATION_TTL_SECONDS,
        is_active,
    )


class InMemorySessionService(SessionPort):
    """Session port adapter backed by user-profile activation and in-memory chat memory."""

    def ensure_active_session(self, session_id: str | None) -> str:
        if not session_id:
            new_session_id = str(uuid.uuid4())
            profile_id = set_active_session_by_session_id(new_session_id)
            if profile_id:
                _set_cached_session_active(new_session_id, True)
                return new_session_id
            return new_session_id

        try:
            is_active = _get_cached_session_active(session_id)
            if is_active is None:
                is_active = is_session_active(session_id)
                _set_cached_session_active(session_id, is_active)
            if not is_active:
                new_session_id = str(uuid.uuid4())
                profile_id = set_active_session_by_session_id(new_session_id)
                if profile_id:
                    _set_cached_session_active(new_session_id, True)
                    return new_session_id
        except NotFoundError:
            new_session_id = str(uuid.uuid4())
            profile_id = set_active_session_by_session_id(new_session_id)
            if profile_id:
                _set_cached_session_active(new_session_id, True)
                return new_session_id
        except Exception as exc:
            raise DependencyError("Failed to validate or activate session") from exc
        return session_id

    def get_or_create_session(self, session_id: str):
        return _get_or_create_conversation_chain(session_id, None)

    def get_recent_messages(self, session_id: str) -> list[dict[str, str]]:
        session = self.get_or_create_session(session_id)
        history = getattr(session.memory.chat_memory, "messages", [])
        normalized = []
        for message in history:
            role = "assistant"
            if "Human" in str(message.__class__):
                role = "user"
            normalized.append({"role": role, "content": getattr(message, "content", "")})
        return normalized

    def append_messages(self, session_id: str, user_message: str, assistant_message: str) -> None:
        session = self.get_or_create_session(session_id)
        session.memory.chat_memory.add_user_message(user_message)
        session.memory.chat_memory.add_ai_message(assistant_message)

    def clear_session(self, session_id: str) -> None:
        _clear_conversation_chain(session_id)

    def clear_all_sessions(self) -> None:
        _conversation_chains.clear()
        _session_validation_cache.clear()


@lru_cache(maxsize=1)
def get_session_service() -> SessionPort:
    """Return the cached session port implementation."""
    return InMemorySessionService()

