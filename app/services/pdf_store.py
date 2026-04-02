"""
PDF storage module: read-only from Assessment pdf_embeddings.
Chatbot does not create or delete embeddings; Assessment pipeline owns ingestion.
"""
import time
from typing import List, Dict, Any
from app.core.exceptions import PersistenceError
from app.utils.logger import logger

_CACHE_TTL_SECONDS = 60
_pdf_exists_cache: dict[str, tuple[float, bool]] = {}
_pdf_count_cache: dict[str, tuple[float, int]] = {}
_pdf_documents_cache: tuple[float, list[dict[str, Any]]] | None = None


def _get_cached_pdf_exists(pdf_id: str) -> bool | None:
    cached = _pdf_exists_cache.get(pdf_id)
    if not cached:
        return None
    expires_at, value = cached
    if expires_at < time.time():
        _pdf_exists_cache.pop(pdf_id, None)
        return None
    return value


def _set_cached_pdf_exists(pdf_id: str, value: bool) -> None:
    _pdf_exists_cache[pdf_id] = (time.time() + _CACHE_TTL_SECONDS, value)


def _get_cached_pdf_count(pdf_id: str) -> int | None:
    cached = _pdf_count_cache.get(pdf_id)
    if not cached:
        return None
    expires_at, value = cached
    if expires_at < time.time():
        _pdf_count_cache.pop(pdf_id, None)
        return None
    return value


def _set_cached_pdf_count(pdf_id: str, value: int) -> None:
    _pdf_count_cache[pdf_id] = (time.time() + _CACHE_TTL_SECONDS, value)


def _get_cached_pdf_documents() -> list[dict[str, Any]] | None:
    global _pdf_documents_cache
    if not _pdf_documents_cache:
        return None
    expires_at, value = _pdf_documents_cache
    if expires_at < time.time():
        _pdf_documents_cache = None
        return None
    return value


def _set_cached_pdf_documents(value: list[dict[str, Any]]) -> None:
    global _pdf_documents_cache
    _pdf_documents_cache = (time.time() + _CACHE_TTL_SECONDS, value)

def _get_supabase_client():
    from app.database.supabase import get_supabase
    return get_supabase()

def store_pdf_embeddings(chunks: List[Dict[str, Any]], table_name: str = "pdf_embeddings") -> int:
    """
    No-op: PDF embeddings are created only by the Assessment pipeline.
    Chatbot does not write to pdf_embeddings.
    """
    if chunks:
        logger.info("PDF embeddings are managed by the Assessment system; skipping chatbot store (%d chunks)", len(chunks))
    return 0

def check_duplicate_pdf(pdf_id: str, table_name: str = "pdf_embeddings") -> bool:
    """Check if PDF exists in Assessment pdf_embeddings (read-only)."""
    cached_exists = _get_cached_pdf_exists(pdf_id)
    if cached_exists is not None:
        return cached_exists
    try:
        supabase_client = _get_supabase_client()
        result = supabase_client.table(table_name).select("pdf_id").eq("pdf_id", pdf_id).limit(1).execute()
        exists = len(result.data) > 0 if result.data else False
        _set_cached_pdf_exists(pdf_id, exists)
        return exists
    except Exception as e:
        logger.error("Failed to check duplicate PDF %s: %s", pdf_id, e)
        raise PersistenceError("Failed to check PDF existence") from e

def delete_pdf_embeddings(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """
    No-op: Chatbot does not delete from Assessment pdf_embeddings.
    Deletion is handled by the Assessment system.
    """
    logger.info("PDF deletion is managed by the Assessment system; skipping chatbot delete for %s", pdf_id)
    return 0

def get_pdf_embeddings_count(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """Count chunks for pdf_id in Assessment pdf_embeddings (read-only)."""
    cached_count = _get_cached_pdf_count(pdf_id)
    if cached_count is not None:
        return cached_count
    try:
        supabase_client = _get_supabase_client()
        result = (
            supabase_client
            .table(table_name)
            .select("pdf_id", count="exact", head=True)
            .eq("pdf_id", pdf_id)
            .execute()
        )
        count = int(getattr(result, "count", 0) or 0)
        _set_cached_pdf_exists(pdf_id, count > 0)
        _set_cached_pdf_count(pdf_id, count)
        return count
    except Exception as e:
        logger.error("Failed to count PDF embeddings for %s: %s", pdf_id, e)
        raise PersistenceError("Failed to retrieve PDF embedding count") from e

def list_pdf_documents(table_name: str = "pdf_embeddings") -> List[Dict[str, Any]]:
    """List PDFs from Assessment pdf_embeddings (pdf_id, pdf_title); no created_at in Assessment schema."""
    cached_documents = _get_cached_pdf_documents()
    if cached_documents is not None:
        return cached_documents
    try:
        supabase_client = _get_supabase_client()
        result = (
            supabase_client
            .table(table_name)
            .select("pdf_id, pdf_title")
            .order("pdf_id")
            .limit(5000)
            .execute()
        )
        if not result.data:
            return []
        documents: list[dict[str, Any]] = []
        current_document: dict[str, Any] | None = None
        for row in result.data:
            pdf_id = row.get("pdf_id")
            if not pdf_id:
                continue
            if current_document is None or current_document["pdf_id"] != pdf_id:
                current_document = {
                    "pdf_id": pdf_id,
                    "pdf_title": row.get("pdf_title", "Unknown"),
                    "embedding_count": 0,
                }
                documents.append(current_document)
            current_document["embedding_count"] += 1
        _set_cached_pdf_documents(documents)
        for document in documents:
            pdf_id = document.get("pdf_id")
            if pdf_id:
                _set_cached_pdf_exists(pdf_id, True)
                _set_cached_pdf_count(pdf_id, int(document.get("embedding_count", 0)))
        return documents
    except Exception as e:
        logger.error("Failed to list PDF documents: %s", e)
        raise PersistenceError("Failed to list PDF documents") from e
