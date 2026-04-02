from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.application.chat.policies import PDF_ONLY_REFUSAL_MESSAGE
from app.application.chat.query_service import ChatQueryService
from app.application.chat.response_builder import ChatResponseBuilder
from app.application.chat.retrieval_service import ChatRetrievalService
from app.application.chat.session_service import ChatSessionService
from app.core.exceptions import DependencyError
from app.models.schemas import ChatRequest
from tests.conftest import (
    DummyDoc,
    StubEmbeddings,
    StubGenerationService,
    StubRetrievalPort,
    StubSessionService,
    StubTrackingService,
)


def _build_service(
    *,
    docs_with_scores=None,
    embeddings_side_effect=None,
    retrieval_side_effect=None,
    generation_answer="Grounded answer",
):
    embeddings = StubEmbeddings(side_effect=embeddings_side_effect)
    retrieval_port = StubRetrievalPort(
        docs_with_scores=docs_with_scores or [],
        side_effect=retrieval_side_effect,
    )
    session_port = StubSessionService()
    generation = StubGenerationService(answer=generation_answer)
    tracking = StubTrackingService()
    service = ChatQueryService(
        embeddings=embeddings,
        retrieval_service=ChatRetrievalService(retrieval_port),
        session_service=ChatSessionService(session_port),
        response_builder=ChatResponseBuilder(generation),
        tracking=tracking,
    )
    return service, embeddings, retrieval_port, session_port, generation, tracking


@pytest.mark.asyncio
async def test_handle_chat_query_valid_flow():
    docs = [
        (
            DummyDoc(
                page_content="Python is a high-level language.",
                metadata={"source_type": "pdf", "pdf_id": "pdf-1", "pdf_title": "Python", "page_number": 1, "chunk_id": 1},
            ),
            0.81,
        ),
        (
            DummyDoc(
                page_content="Python supports variables, loops, and functions.",
                metadata={"source_type": "pdf", "pdf_id": "pdf-1", "pdf_title": "Python", "page_number": 2, "chunk_id": 2},
            ),
            0.76,
        )
    ]
    service, embeddings, retrieval_port, session_port, generation, tracking = _build_service(docs_with_scores=docs)

    response = await service.handle_chat_query(ChatRequest(query="What is Python?", user_id="user-1"))

    assert response.answer == "Grounded answer"
    assert response.conversation_id == "generated-session"
    assert len(response.sources) == 2
    assert embeddings.calls == ["What is Python?"]
    assert retrieval_port.calls[0][1] == 10
    assert session_port.append_messages_calls == [("generated-session", "What is Python?", "Grounded answer")]
    assert generation.calls
    tracking.track_chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_chat_query_partial_flow_with_moderate_evidence():
    docs = [
        (
            DummyDoc(
                page_content="Python lists can store multiple values.",
                metadata={"source_type": "pdf", "pdf_id": "pdf-2", "pdf_title": "Python Lists", "page_number": 1, "chunk_id": 1},
            ),
            0.39,
        ),
        (
            DummyDoc(
                page_content="Lists can be indexed and iterated in Python.",
                metadata={"source_type": "pdf", "pdf_id": "pdf-2", "pdf_title": "Python Lists", "page_number": 2, "chunk_id": 2},
            ),
            0.34,
        ),
    ]
    service, _embeddings, _retrieval_port, session_port, generation, tracking = _build_service(docs_with_scores=docs)

    response = await service.handle_chat_query(ChatRequest(query="Explain Python lists"))

    assert response.answer == "Grounded answer"
    assert response.sources
    assert generation.calls
    assert session_port.append_messages_calls
    tracking.track_chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_chat_query_greeting_flow_skips_retrieval_and_generation():
    service, embeddings, retrieval_port, _session_port, generation, tracking = _build_service()

    response = await service.handle_chat_query(ChatRequest(query="hi"))

    assert isinstance(response.answer, str)
    assert response.answer
    assert response.sources == []
    assert embeddings.calls == []
    assert retrieval_port.calls == []
    assert generation.calls == []
    tracking.track_chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_chat_query_partial_flow_for_weak_retrieved_data():
    docs = [
        (
            DummyDoc(
                page_content="Weakly related content",
                metadata={"source_type": "pdf", "pdf_id": "pdf-1", "pdf_title": "Python", "page_number": 1, "chunk_id": 1},
            ),
            0.10,
        )
    ]
    service, _embeddings, _retrieval_port, session_port, generation, tracking = _build_service(docs_with_scores=docs)

    response = await service.handle_chat_query(ChatRequest(query="What is Java?"))

    assert response.answer == "Grounded answer"
    assert generation.calls
    assert response.sources == []
    assert session_port.append_messages_calls
    tracking.track_chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_chat_query_dependency_error_maps_to_503():
    service, *_ = _build_service(embeddings_side_effect=DependencyError("OpenAI unavailable"))

    with pytest.raises(HTTPException) as exc_info:
        await service.handle_chat_query(ChatRequest(query="What is Python?"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Service temporarily unavailable"


@pytest.mark.asyncio
async def test_handle_chat_query_unexpected_error_maps_to_500():
    service, *_ = _build_service(retrieval_side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc_info:
        await service.handle_chat_query(ChatRequest(query="What is Python?"))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal server error"

