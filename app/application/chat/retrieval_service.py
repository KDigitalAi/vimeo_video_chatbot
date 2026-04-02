"""Application retrieval orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.chat.policies import RetrievalQuality, RetrievalThresholds, compute_retrieval_quality, resolve_thresholds
from app.application.ports.retrieval_port import RetrievalPort


@dataclass
class RetrievalResult:
    docs_with_scores: list[tuple[Any, float]]
    retrieval_best: float | None
    retrieval_used_degraded_fallback: bool
    thresholds: RetrievalThresholds
    quality: RetrievalQuality


class ChatRetrievalService:
    def __init__(self, retrieval_port: RetrievalPort):
        self._retrieval_port = retrieval_port

    def retrieve(self, *, query_embedding: list[float], top_k: int) -> RetrievalResult:
        docs_with_scores = self._retrieval_port.retrieve(query_embedding, max(top_k or 10, 10))
        retrieval_best = max((score for _, score in docs_with_scores), default=None)
        retrieval_used_degraded_fallback = any(
            bool((getattr(doc, "metadata", None) or {}).get("retrieval_degraded"))
            for doc, _score in docs_with_scores
        )
        thresholds = resolve_thresholds(retrieval_used_degraded_fallback)
        quality = compute_retrieval_quality(
            docs_with_scores,
            retrieval_best,
            retrieval_used_degraded_fallback,
        )
        return RetrievalResult(
            docs_with_scores=docs_with_scores,
            retrieval_best=retrieval_best,
            retrieval_used_degraded_fallback=retrieval_used_degraded_fallback,
            thresholds=thresholds,
            quality=quality,
        )
