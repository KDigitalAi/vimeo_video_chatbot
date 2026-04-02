"""Session port contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SessionPort(ABC):
    @abstractmethod
    def ensure_active_session(self, session_id: str | None) -> str:
        """Return a valid active session id."""

    @abstractmethod
    def get_or_create_session(self, session_id: str) -> Any:
        """Return the in-memory conversation session handle."""

    @abstractmethod
    def get_recent_messages(self, session_id: str) -> list[dict[str, str]]:
        """Return recent session messages in chronological order."""

    @abstractmethod
    def append_messages(self, session_id: str, user_message: str, assistant_message: str) -> None:
        """Append the latest user and assistant messages to session memory."""

    @abstractmethod
    def clear_session(self, session_id: str) -> None:
        """Clear session memory."""

    @abstractmethod
    def clear_all_sessions(self) -> None:
        """Clear all in-memory sessions."""
