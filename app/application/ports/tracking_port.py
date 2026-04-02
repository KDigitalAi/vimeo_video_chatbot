"""Tracking port contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TrackingPort(ABC):
    @abstractmethod
    async def track_chat(
        self,
        *,
        user_id: str,
        session_id: str,
        query_text: str,
        answer: str,
        query_embedding: list[float] | None,
        sources: list[dict[str, Any]],
    ) -> None:
        """Persist or dispatch chat tracking."""
