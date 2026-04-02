"""Pure chat policies and business rules."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

PDF_ONLY_REFUSAL_MESSAGE = (
    "Sorry, I can only answer questions related to the available PDF study materials."
)

RAG_HIGH_CONFIDENCE_SCORE = 0.45
RAG_MIN_RELEVANCE_THRESHOLD = 0.25
RAG_MIN_CONTEXT_CHARS = 80
RAG_MIN_SUPPORTING_CHUNKS = 2
QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "give", "how", "i", "if", "in", "is", "it", "me", "more", "of", "on",
    "or", "please", "show", "tell", "that", "the", "this", "to", "what", "when",
    "where", "which", "who", "why", "with", "you", "your", "explain",
}

GREETING_KEYWORDS = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "greetings",
    "howdy",
    "how are you",
    "what's up",
    "sup",
    "yo",
    "good day",
    "good night",
    "greeting",
    "hiya",
    "hey there",
    "hii",
    "helloo",
    "heyy",
    "heyyy",
)

GREETING_RESPONSES = (
    "Hello! I'm your Learning Assistant. How can I help you with your study materials today?",
    "Hi there! I'm ready to help you learn — what topic would you like to explore?",
    "Good morning! Let's study together — what would you like to know today?",
    "Hey! I'm here to help you understand your PDF content. What would you like to learn about?",
    "Hello! Welcome to your study companion. I can help you find information in your uploaded materials. What interests you?",
    "Hi! I'm your educational assistant. Ready to dive into your learning materials — what's on your mind?",
)

FOLLOW_UP_KEYWORDS = (
    "explain more",
    "tell me more",
    "give more",
    "add more",
    "show more",
    "can you explain",
    "elaborate",
    "expand on",
    "go into detail",
    "more examples",
    "more code",
    "more details",
    "further explanation",
    "what else",
    "anything else",
    "other examples",
    "additional",
    "give some more",
    "show some more",
    "provide more",
    "can you explain more",
    "show some examples",
    "explain clearly",
    "give more details",
    "show more codes",
    "expand on this",
    "explain in detail",
)


@dataclass(frozen=True)
class RetrievalThresholds:
    min_relevance: float
    high_confidence: float


@dataclass
class GatingDecision:
    relevant_docs: list[tuple[Any, float]]
    should_refuse: bool
    answer: str | None = None
    sources: list[dict[str, Any]] | None = None
    is_hybrid_context: bool = False
    mode: str = "refuse"
    reason: str = "insufficient_evidence"


@dataclass(frozen=True)
class RetrievalQuality:
    best_score: float | None
    avg_top3_score: float
    num_chunks: int
    degraded_fallback: bool


def is_greeting(query: str) -> bool:
    query_lower = (query or "").lower().strip()
    return any(
        keyword == query_lower
        or query_lower.startswith(keyword + " ")
        or (query_lower.startswith(keyword) and len(query_lower) <= len(keyword) + 2)
        for keyword in GREETING_KEYWORDS
    )


def is_follow_up_query(query: str) -> bool:
    query_lower = (query or "").lower()
    return any(keyword in query_lower for keyword in FOLLOW_UP_KEYWORDS)


def resolve_thresholds(retrieval_used_degraded_fallback: bool) -> RetrievalThresholds:
    if retrieval_used_degraded_fallback:
        return RetrievalThresholds(
            min_relevance=max(RAG_MIN_RELEVANCE_THRESHOLD, 0.35),
            high_confidence=max(RAG_HIGH_CONFIDENCE_SCORE, 0.50),
        )
    return RetrievalThresholds(
        min_relevance=RAG_MIN_RELEVANCE_THRESHOLD,
        high_confidence=RAG_HIGH_CONFIDENCE_SCORE,
    )


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return int(str(value).strip())
    except Exception:
        return default


def compute_retrieval_quality(
    docs_with_scores: list[tuple[Any, float]],
    retrieval_best: float | None,
    degraded_fallback: bool,
) -> RetrievalQuality:
    top3_scores = [score for _doc, score in sorted(docs_with_scores, key=lambda item: item[1], reverse=True)[:3]]
    avg_top3_score = sum(top3_scores) / len(top3_scores) if top3_scores else 0.0
    return RetrievalQuality(
        best_score=retrieval_best,
        avg_top3_score=avg_top3_score,
        num_chunks=len(docs_with_scores),
        degraded_fallback=degraded_fallback,
    )


def _extract_query_keywords(query: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", (query or "").lower())
    return {token for token in tokens if token not in QUERY_STOPWORDS}


def _topic_matches_query(query: str, relevant_docs: list[tuple[Any, float]]) -> bool:
    keywords = _extract_query_keywords(query)
    if not keywords:
        return True
    combined_content = " ".join(
        (getattr(doc, "page_content", None) or "")
        for doc, _score in relevant_docs
    ).lower()
    if not combined_content.strip():
        return False
    matched_keywords = sum(1 for keyword in keywords if keyword in combined_content)
    return matched_keywords >= 1


def apply_gating_policy(
    query: str,
    docs_with_scores: list[tuple[Any, float]],
    retrieval_quality: RetrievalQuality,
    thresholds: RetrievalThresholds,
) -> GatingDecision:
    sorted_docs = sorted(docs_with_scores, key=lambda item: item[1], reverse=True)
    strong_docs = [item for item in sorted_docs if item[1] >= thresholds.high_confidence]
    relevant_docs = [item for item in sorted_docs if item[1] >= thresholds.min_relevance] or sorted_docs[:3]

    if relevant_docs:
        top_doc, _ = relevant_docs[0]
        top_metadata = getattr(top_doc, "metadata", {}) or {}
        pdf_id = top_metadata.get("pdf_id")
        if top_metadata.get("source_type") == "pdf" and pdf_id:
            additional_chunks = []
            seen_chunk_keys = {
                (
                    (getattr(existing_doc, "metadata", {}) or {}).get("pdf_id"),
                    (getattr(existing_doc, "metadata", {}) or {}).get("chunk_id"),
                    (getattr(existing_doc, "metadata", {}) or {}).get("page_number"),
                )
                for existing_doc, _existing_score in relevant_docs
            }
            for doc, score in docs_with_scores:
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_key = (
                    metadata.get("pdf_id"),
                    metadata.get("chunk_id"),
                    metadata.get("page_number"),
                )
                if (
                    metadata.get("source_type") == "pdf"
                    and metadata.get("pdf_id") == pdf_id
                    and score >= thresholds.min_relevance
                    and chunk_key not in seen_chunk_keys
                ):
                    additional_chunks.append((doc, score))
                    seen_chunk_keys.add(chunk_key)

            if additional_chunks:
                additional_chunks.sort(
                    key=lambda item: (
                        _safe_int(getattr(item[0], "metadata", {}).get("page_number"), 0),
                        _safe_int(getattr(item[0], "metadata", {}).get("chunk_id"), 0),
                    )
                )
                relevant_docs.extend(additional_chunks[:8])

    if not docs_with_scores:
        return GatingDecision(
            relevant_docs=[],
            should_refuse=True,
            answer=PDF_ONLY_REFUSAL_MESSAGE,
            sources=[],
            mode="refuse",
            reason="no_documents",
        )

    if retrieval_quality.best_score is None or not relevant_docs:
        return GatingDecision(
            relevant_docs=relevant_docs,
            should_refuse=True,
            answer=PDF_ONLY_REFUSAL_MESSAGE,
            sources=[],
            mode="refuse",
            reason="no_relevant_docs",
        )

    if retrieval_quality.best_score < 0.05 and retrieval_quality.avg_top3_score < 0.05:
        return GatingDecision(
            relevant_docs=relevant_docs,
            should_refuse=True,
            answer=PDF_ONLY_REFUSAL_MESSAGE,
            sources=[],
            mode="refuse",
            reason="extremely_low_scores",
        )

    mode = "partial"
    reason = "partial_evidence"
    if (
        retrieval_quality.best_score >= thresholds.high_confidence
        and len(strong_docs) >= RAG_MIN_SUPPORTING_CHUNKS
        and len(relevant_docs) >= RAG_MIN_SUPPORTING_CHUNKS
    ):
        mode = "strict"
        reason = "strong_evidence"

    return GatingDecision(
        relevant_docs=relevant_docs,
        should_refuse=False,
        is_hybrid_context=mode == "partial",
        mode=mode,
        reason=reason,
    )
