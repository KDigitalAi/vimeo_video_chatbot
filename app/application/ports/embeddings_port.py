"""Embeddings port contract."""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingsPort(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Return an embedding vector for the query text."""
