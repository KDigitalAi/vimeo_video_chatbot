"""Grounded generation adapter behind the generation port."""
from __future__ import annotations

from functools import lru_cache

from app.application.chat.policies import PDF_ONLY_REFUSAL_MESSAGE
from app.application.ports.generation_port import GenerationPort
from app.services.chat_generation import (
    build_context_from_docs,
    build_follow_up_topic_hint,
    format_educational_response,
    generate_context_grounded_response,
)
from app.utils.runtime_helpers import get_logger_safe

logger = get_logger_safe(__name__)


class GroundedGenerationService(GenerationPort):
    def generate_answer(
        self,
        *,
        query: str,
        relevant_docs,
        retrieval_best: float,
        high_confidence_threshold: float,
        conversation_session: object | None,
        is_follow_up: bool,
    ) -> str:
        context = build_context_from_docs(relevant_docs)
        if not (context or "").strip():
            return PDF_ONLY_REFUSAL_MESSAGE

        topic_hint = build_follow_up_topic_hint(conversation_session) if is_follow_up else "\n"
        is_hybrid_context = retrieval_best < high_confidence_threshold

        try:
            if is_hybrid_context:
                raw_answer = generate_context_grounded_response(
                    query,
                    context,
                    is_hybrid_context=True,
                    is_follow_up=is_follow_up,
                    topic_hint=topic_hint,
                )
                if (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip():
                    return PDF_ONLY_REFUSAL_MESSAGE
                return format_educational_response(
                    raw_answer,
                    query,
                    has_relevant_docs=True,
                    hybrid_weak_context=True,
                )

            raw_answer = generate_context_grounded_response(
                query,
                context,
                is_hybrid_context=False,
                is_follow_up=is_follow_up,
                topic_hint=topic_hint,
            )
            if (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip():
                return PDF_ONLY_REFUSAL_MESSAGE
            return format_educational_response(raw_answer, query, has_relevant_docs=True)
        except Exception as exc:
            logger.error("Primary answer generation failed: %s", exc)
            return PDF_ONLY_REFUSAL_MESSAGE


@lru_cache(maxsize=1)
def get_generation_service() -> GenerationPort:
    return GroundedGenerationService()
