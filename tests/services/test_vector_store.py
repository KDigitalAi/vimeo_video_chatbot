from __future__ import annotations

from app.services.vector_store import SupabaseVectorStore


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeRpcCall:
    def __init__(self, data=None, error=None):
        self._data = data
        self._error = error

    def execute(self):
        if self._error:
            raise self._error
        return FakeExecuteResult(self._data)


class FakeTableQuery:
    def __init__(self, data):
        self._data = data

    def select(self, _columns):
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return FakeExecuteResult(self._data)


class FakeSupabase:
    def __init__(self, *, rpc_data=None, rpc_error=None, table_data=None):
        self.rpc_data = rpc_data
        self.rpc_error = rpc_error
        self.table_data = table_data or []

    def rpc(self, _name, _payload):
        return FakeRpcCall(self.rpc_data, self.rpc_error)

    def table(self, _name):
        return FakeTableQuery(self.table_data)


def test_vector_store_rpc_success(monkeypatch):
    import app.services.vector_store as vector_store_module

    monkeypatch.setattr(
        vector_store_module,
        "_get_supabase",
        lambda: FakeSupabase(
            rpc_data=[
                {
                    "content": "Python intro",
                    "chunk_id": 2,
                    "pdf_id": "pdf-1",
                    "pdf_title": "Python Basics",
                    "page_number": 1,
                    "similarity": 0.9,
                }
            ]
        ),
    )

    store = SupabaseVectorStore()
    results = store.similarity_search_by_vector_with_relevance_scores([0.1, 0.2, 0.3], k=3)

    assert len(results) == 1
    doc, score = results[0]
    assert doc.page_content == "Python intro"
    assert doc.metadata["retrieval_mode"] == "rpc"
    assert doc.metadata["retrieval_degraded"] is False
    assert score == 0.9


def test_vector_store_rpc_empty_uses_fallback(monkeypatch):
    import app.services.vector_store as vector_store_module

    monkeypatch.setattr(
        vector_store_module,
        "_get_supabase",
        lambda: FakeSupabase(
            rpc_data=[],
            table_data=[
                {
                    "chunk_text": "Fallback python content",
                    "embedding": [1.0, 0.0, 0.0],
                    "pdf_id": "pdf-2",
                    "pdf_title": "Fallback PDF",
                    "chunk_index": 4,
                    "page_number": 3,
                },
                {
                    "chunk_text": "Fallback python example",
                    "embedding": [0.95, 0.0, 0.0],
                    "pdf_id": "pdf-2",
                    "pdf_title": "Fallback PDF",
                    "chunk_index": 5,
                    "page_number": 4,
                }
            ],
        ),
    )

    store = SupabaseVectorStore()
    results = store.similarity_search_by_vector_with_relevance_scores([1.0, 0.0, 0.0], k=2)

    assert len(results) == 2
    doc, score = results[0]
    assert doc.metadata["retrieval_mode"] == "fallback"
    assert doc.metadata["retrieval_degraded"] is True
    assert score >= 0.45


def test_vector_store_rpc_failure_allows_fallback_results(monkeypatch):
    import app.services.vector_store as vector_store_module

    monkeypatch.setattr(
        vector_store_module,
        "_get_supabase",
        lambda: FakeSupabase(
            rpc_error=RuntimeError("rpc failed"),
            table_data=[
                {
                    "chunk_text": "Fallback content",
                    "embedding": [0.0, 1.0, 0.0],
                    "pdf_id": "pdf-3",
                    "pdf_title": "Fallback",
                    "chunk_index": 1,
                    "page_number": 1,
                }
            ],
        ),
    )

    store = SupabaseVectorStore()
    results = store.similarity_search_by_vector_with_relevance_scores([0.0, 1.0, 0.0], k=1)

    assert len(results) == 1
    assert results[0][0].metadata["retrieval_degraded"] is True


def test_vector_store_skips_malformed_and_dimension_mismatch_embeddings(monkeypatch):
    import app.services.vector_store as vector_store_module

    monkeypatch.setattr(
        vector_store_module,
        "_get_supabase",
        lambda: FakeSupabase(
            rpc_data=[],
            table_data=[
                {"chunk_text": "bad", "embedding": "not-a-vector", "pdf_id": "pdf-1", "pdf_title": "Bad", "chunk_index": 1, "page_number": 1},
                {"chunk_text": "wrong-dim", "embedding": [1.0, 2.0], "pdf_id": "pdf-1", "pdf_title": "Wrong", "chunk_index": 2, "page_number": 1},
                {"chunk_text": "good", "embedding": [0.0, 0.0, 1.0], "pdf_id": "pdf-1", "pdf_title": "Good", "chunk_index": 3, "page_number": 1},
            ],
        ),
    )

    store = SupabaseVectorStore()
    results = store.similarity_search_by_vector_with_relevance_scores([0.0, 0.0, 1.0], k=3)

    assert len(results) == 1
    assert results[0][0].page_content == "good"


def test_vector_store_returns_empty_when_no_rpc_or_fallback_results(monkeypatch):
    import app.services.vector_store as vector_store_module

    monkeypatch.setattr(
        vector_store_module,
        "_get_supabase",
        lambda: FakeSupabase(rpc_data=[], table_data=[]),
    )

    store = SupabaseVectorStore()

    assert store.similarity_search_by_vector_with_relevance_scores([0.1, 0.2, 0.3], k=3) == []

