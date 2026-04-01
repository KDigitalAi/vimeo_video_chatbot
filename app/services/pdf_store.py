"""
PDF storage module: read-only from Assessment pdf_embeddings.
Chatbot does not create or delete embeddings; Assessment pipeline owns ingestion.
"""
from typing import List, Dict, Any
from app.utils.logger import logger

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
    try:
        supabase_client = _get_supabase_client()
        result = supabase_client.table(table_name).select("pdf_id").eq("pdf_id", pdf_id).limit(1).execute()
        return len(result.data) > 0 if result.data else False
    except Exception as e:
        logger.error("Failed to check duplicate PDF %s: %s", pdf_id, e)
        return False

def delete_pdf_embeddings(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """
    No-op: Chatbot does not delete from Assessment pdf_embeddings.
    Deletion is handled by the Assessment system.
    """
    logger.info("PDF deletion is managed by the Assessment system; skipping chatbot delete for %s", pdf_id)
    return 0

def get_pdf_embeddings_count(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """Count chunks for pdf_id in Assessment pdf_embeddings (read-only)."""
    try:
        supabase_client = _get_supabase_client()
        result = supabase_client.table(table_name).select("pdf_id").eq("pdf_id", pdf_id).execute()
        return len(result.data) if result.data else 0
    except Exception as e:
        logger.error("Failed to count PDF embeddings for %s: %s", pdf_id, e)
        return 0

def list_pdf_documents(table_name: str = "pdf_embeddings") -> List[Dict[str, Any]]:
    """List PDFs from Assessment pdf_embeddings (pdf_id, pdf_title); no created_at in Assessment schema."""
    try:
        supabase_client = _get_supabase_client()
        result = supabase_client.table(table_name).select("pdf_id, pdf_title").execute()
        if not result.data:
            return []
        pdf_docs = {}
        for row in result.data:
            pdf_id = row.get("pdf_id")
            if pdf_id not in pdf_docs:
                pdf_docs[pdf_id] = {
                    "pdf_id": pdf_id,
                    "pdf_title": row.get("pdf_title", "Unknown"),
                    "embedding_count": 0
                }
            pdf_docs[pdf_id]["embedding_count"] += 1
        return list(pdf_docs.values())
    except Exception as e:
        logger.error("Failed to list PDF documents: %s", e)
        return []
