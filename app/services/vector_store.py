"""
Lightweight Supabase-backed vector store shim to satisfy chat.py expectations.
Reads from Assessment pdf_embeddings (chunk_text, chunk_index) via RPC or select.
Mapping: content = chunk_text, chunk_id = chunk_index. Chatbot does not create embeddings.
"""
from typing import List, Tuple, Any
from functools import lru_cache
from app.application.ports.retrieval_port import RetrievalPort
from app.utils.logger import logger


def _get_supabase():
    """Lazy import of Supabase client with error handling."""
    try:
        from app.database.supabase import get_supabase
        return get_supabase()
    except Exception as e:
        logger.exception(
            "Failed to get Supabase client",
            component="vector_store",
            operation="get_supabase_client",
            result="failure",
        )
        raise


def _cosine_similarity(a: list, b: list) -> float:
    try:
        import numpy as np

        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        denom = (np.linalg.norm(va) * np.linalg.norm(vb))
        if denom == 0:
            return 0.0
        return float(np.dot(va, vb) / denom)
    except Exception:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


def _parse_embedding(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            s = value.strip().strip("[]")
            if not s:
                return []
            return [float(x.strip()) for x in s.split(",")]
        except Exception:
            return []
    # Supabase/Postgrest sometimes returns vector as dict (e.g. {"value": "[...]"} or similar)
    if isinstance(value, dict):
        for key in ("value", "embedding", "vector", "data"):
            if key in value and value[key] is not None:
                return _parse_embedding(value[key])
    return []


def _build_fallback_document(row: dict, score: float, fallback_reason: str):
    """Create a lightweight fallback document tuple."""
    return (
        _SimpleDocument(
            page_content=row.get("chunk_text") or "",
            metadata={
                "source_type": "pdf",
                "pdf_id": row.get("pdf_id"),
                "pdf_title": row.get("pdf_title"),
                "page_number": row.get("page_number"),
                "chunk_id": row.get("chunk_index"),
                "folder": row.get("folder"),
                "retrieval_mode": "fallback",
                "retrieval_degraded": True,
                "fallback_reason": fallback_reason,
            },
        ),
        score,
    )


def _row_to_content_and_metadata(row: dict) -> tuple:
    """
    Map pdf_embeddings row to chatbot document shape.
    Database (Assessment) uses: chunk_text, chunk_index.
    Chatbot expects: page_content (content), metadata.chunk_id.
    Mapping: content = chunk_text, chunk_id = chunk_index.
    RPC returns aliased columns (content, chunk_id); raw select returns chunk_text, chunk_index.
    """
    content = row.get("chunk_text") or row.get("content") or ""
    chunk_id = row.get("chunk_index") if row.get("chunk_index") is not None else row.get("chunk_id")
    return content, {
        "source_type": "pdf",
        "pdf_id": row.get("pdf_id"),
        "pdf_title": row.get("pdf_title"),
        "page_number": row.get("page_number"),
        "chunk_id": chunk_id,
        "folder": row.get("folder"),
    }


class _SimpleDocument:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class SupabaseVectorStore:
    def __init__(self):
        try:
            self._supabase = _get_supabase()
        except Exception as e:
            logger.exception(
                "Failed to initialize vector store",
                component="vector_store",
                operation="initialize",
                result="failure",
            )
            raise ValueError(f"Cannot initialize vector store: {str(e)}") from e

    def similarity_search_by_vector_with_relevance_scores(self, query_embedding: list, k: int = 5) -> List[Tuple[_SimpleDocument, float]]:
        results: List[Tuple[_SimpleDocument, float]] = []
        try:
            # Prefer RPC: vector search in DB on Assessment pdf_embeddings (chunk_text, chunk_index)
            rpc_rows = self._search_via_rpc(query_embedding, k)
            if rpc_rows is not None and len(rpc_rows) > 0:
                for row in rpc_rows:
                    content, meta = _row_to_content_and_metadata(row)
                    meta["retrieval_mode"] = "rpc"
                    meta["retrieval_degraded"] = False
                    score = float(row.get("similarity", 0.0))
                    results.append((_SimpleDocument(page_content=content, metadata=meta), score))
                results.sort(key=lambda x: x[1], reverse=True)
                logger.info(
                    "Vector retrieval completed via RPC",
                    component="vector_store",
                    operation="retrieve",
                    result="success",
                    retrieval_mode="rpc",
                    result_count=len(results[:k]),
                    degraded_fallback=False,
                )
                return results[:k]

            fallback_reason = "rpc_empty"
            if rpc_rows is not None and len(rpc_rows) == 0:
                logger.warning(
                    "RPC match_pdf_embeddings returned 0 rows (threshold/no match). "
                    "Trying DEGRADED PostgREST fallback; results are not semantically ordered and must be treated as low confidence. "
                    "Deploy SQL match_pdf_embeddings floor should match chat RAG_MIN_RELEVANCE_THRESHOLD. "
                    "query_embedding_dim=%d",
                    len(query_embedding),
                    component="vector_store",
                    operation="fallback_retrieval",
                    result="empty",
                    degraded_fallback=True,
                )

            # Fallback needs a wider pool because raw table rows are not semantically ordered.
            fetch_limit = max(100, min(k * 20, 200))
            logger.info(
                "Using table: pdf_embeddings",
                component="vector_store",
                operation="fallback_retrieval",
                result="table_selected",
            )
            pdf_rows = self._supabase.table("pdf_embeddings").select(
                "chunk_text, embedding, pdf_id, pdf_title, chunk_index, page_number"
            ).limit(fetch_limit).execute().data or []

            if not pdf_rows:
                logger.warning(
                    "No PDF embeddings found. Ensure pdf_embeddings has data and columns: "
                    "chunk_text, embedding, pdf_id, pdf_title, chunk_index, page_number.",
                    component="vector_store",
                    operation="fallback_retrieval",
                    result="empty",
                    degraded_fallback=True,
                )
                return []

            qdim = len(query_embedding)
            skipped_dim = 0
            skipped_empty = 0
            skipped_low_score = 0
            sample_stored_dim = None
            scored_candidates: List[Tuple[_SimpleDocument, float]] = []

            for row in pdf_rows:
                emb = _parse_embedding(row.get("embedding"))
                if not emb:
                    skipped_empty += 1
                    continue
                if len(emb) != qdim:
                    skipped_dim += 1
                    if sample_stored_dim is None:
                        sample_stored_dim = len(emb)
                    continue
                score = _cosine_similarity(query_embedding, emb)
                scored_candidates.append(_build_fallback_document(row, score, fallback_reason))

            if scored_candidates:
                scored_candidates.sort(key=lambda item: item[1], reverse=True)
                results = scored_candidates[:k]
                best_fallback_score = results[0][1] if results else 0.0
                avg_top3_score = (
                    sum(score for _doc, score in results[:3]) / min(len(results), 3)
                    if results else 0.0
                )
                logger.info(
                    "Vector retrieval completed via fallback",
                    component="vector_store",
                    operation="retrieve",
                    result="success",
                    retrieval_mode="fallback",
                    result_count=len(results),
                    degraded_fallback=True,
                    best_score=best_fallback_score,
                    avg_top3_score=avg_top3_score,
                    rows_fetched=len(pdf_rows),
                )

            if not results and pdf_rows:
                logger.error(
                    "pdf_embeddings fallback produced NO scored rows: rows_fetched=%d query_dim=%d "
                    "skipped_empty_emb=%d skipped_dimension_mismatch=%d skipped_low_score=%d sample_stored_dim=%s "
                    "— align EMBEDDING_MODEL/dimensions with ingestion or widen RPC/fallback pool.",
                    len(pdf_rows),
                    qdim,
                    skipped_empty,
                    skipped_dim,
                    skipped_low_score,
                    sample_stored_dim,
                    component="vector_store",
                    operation="fallback_retrieval",
                    result="failure",
                    degraded_fallback=True,
)

            # Keep only top-k degraded candidates as early as possible to minimize work.
            return results

        except Exception as e:
            logger.exception(
                "Vector retrieval failed",
                component="vector_store",
                operation="retrieve",
                result="failure",
            )
            return []

    def _search_via_rpc(self, query_embedding: list, k: int):
        """Call match_pdf_embeddings RPC (reads Assessment pdf_embeddings, returns content/chunk_id)."""
        try:
            # Postgrest often expects vector as string for pgvector
            vec_str = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
            resp = self._supabase.rpc(
                "match_pdf_embeddings",
                {"query_embedding": vec_str, "match_count": k}
            ).execute()
            if resp.data and len(resp.data) > 0:
                logger.info(
                    "Vector RPC search succeeded",
                    component="vector_store",
                    operation="rpc_retrieval",
                    result="success",
                    result_count=len(resp.data),
                    degraded_fallback=False,
                )
                return resp.data
            # Return empty list so caller can try fallback (RPC succeeded but no rows)
            logger.info(
                "Vector RPC search returned no rows",
                component="vector_store",
                operation="rpc_retrieval",
                result="empty",
                result_count=0,
                degraded_fallback=False,
            )
            return resp.data if resp.data is not None else []
        except Exception as e:
            logger.warning(
                "RPC match_pdf_embeddings FAILED; switching to DEGRADED fallback retrieval: %s. "
                "Fallback is unordered and must not be treated as equivalent to RPC vector search. "
                "Ensure chatbot migrations are run and pdf_embeddings has columns chunk_text, chunk_index.",
                e,
                component="vector_store",
                operation="fallback_retrieval",
                result="fallback",
                error_type=type(e).__name__,
                degraded_fallback=True,
            )
            return None

def load_supabase_vectorstore() -> SupabaseVectorStore:
    return SupabaseVectorStore()


class SupabaseRetrievalService(RetrievalPort):
    """Retrieval port adapter backed by Supabase vector search."""

    def __init__(self):
        self._vector_store = load_supabase_vectorstore()

    def retrieve(self, query_embedding: list[float], k: int) -> list[tuple[Any, float]]:
        return self._vector_store.similarity_search_by_vector_with_relevance_scores(
            query_embedding,
            k=k,
        )


@lru_cache(maxsize=1)
def get_retrieval_service() -> RetrievalPort:
    """Return the cached retrieval port implementation."""
    return SupabaseRetrievalService()


