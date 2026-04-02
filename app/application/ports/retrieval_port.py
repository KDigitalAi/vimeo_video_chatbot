"""Retrieval port contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RetrievalPort(ABC):
    @abstractmethod
    def retrieve(self, query_embedding: list[float], k: int) -> list[tuple[Any, float]]:
        """Return retrieved documents with relevance scores."""
