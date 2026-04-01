"""
In-memory chat session memory and lifecycle helpers.
"""
from __future__ import annotations

import time

# In-memory session storage limits to prevent unbounded growth.
MAX_IN_MEMORY_SESSIONS = 100
MAX_SESSION_MESSAGES = 20
SESSION_TTL_SECONDS = 60 * 60

# Global dictionary to store conversation chains per session
_conversation_chains = {}


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

