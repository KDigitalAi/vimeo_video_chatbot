"""Chat response generation and response assembly."""
from __future__ import annotations

from app.application.chat.policies import PDF_ONLY_REFUSAL_MESSAGE, RetrievalThresholds
from app.application.ports.generation_port import GenerationPort
from app.models.schemas import ChatRequest, ChatResponse


class ChatResponseBuilder:
    def __init__(self, generation_service: GenerationPort):
        self._generation_service = generation_service

    def build_response(
        self,
        *,
        answer: str,
        sources: list[dict],
        session_id: str,
        processing_time: float,
    ) -> ChatResponse:
        return ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=session_id,
            processing_time=processing_time,
            tokens_used=None,
        )

    def build_sources(
        self,
        *,
        request: ChatRequest,
        relevant_docs: list[tuple[object, float]],
        thresholds: RetrievalThresholds,
        answer: str,
    ) -> list[dict]:
        sources = []
        if request.include_sources and relevant_docs and answer != PDF_ONLY_REFUSAL_MESSAGE:
            seen = set()
            for doc, score in sorted(relevant_docs, key=lambda item: item[1], reverse=True):
                if score < thresholds.min_relevance:
                    continue
                metadata = getattr(doc, "metadata", None) or {}
                if metadata.get("source_type", "pdf") != "pdf":
                    continue
                key = (metadata.get("pdf_id"), metadata.get("chunk_id"), metadata.get("page_number"))
                if key in seen:
                    continue
                seen.add(key)
                source_name = metadata.get("pdf_title", "Unknown PDF")
                sources.append(
                    {
                        "source_type": "pdf",
                        "pdf_title": source_name,
                        "pdf_id": metadata.get("pdf_id"),
                        "page_number": metadata.get("page_number"),
                        "chunk_id": metadata.get("chunk_id"),
                        "relevance_score": score,
                        "source_name": source_name,
                    }
                )
        return sources

    def generate_answer(
        self,
        *,
        request: ChatRequest,
        relevant_docs: list[tuple[object, float]],
        thresholds: RetrievalThresholds,
        retrieval_best: float,
        conversation_session: object | None,
        is_follow_up: bool,
    ) -> str:
        return self._generation_service.generate_answer(
            query=request.query,
            relevant_docs=relevant_docs,
            retrieval_best=retrieval_best,
            high_confidence_threshold=thresholds.high_confidence,
            conversation_session=conversation_session,
            is_follow_up=is_follow_up,
        )
