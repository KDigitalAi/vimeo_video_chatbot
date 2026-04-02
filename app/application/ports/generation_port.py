"""Generation port contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GenerationPort(ABC):
    @abstractmethod
    def generate_answer(
        self,
        *,
        query: str,
        relevant_docs: list[tuple[Any, float]],
        retrieval_best: float,
        high_confidence_threshold: float,
        conversation_session: object | None,
        is_follow_up: bool,
    ) -> str:
        """Generate the final grounded answer for the query."""
