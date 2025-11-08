"""
PDF storage module for managing PDF embeddings in Supabase.
Simplified to use the unified vector store functionality.
"""
from typing import List, Dict, Any
from app.services.vector_store_direct import store_embeddings_directly
from app.utils.logger import logger

def store_pdf_embeddings(chunks: List[Dict[str, Any]], table_name: str = "pdf_embeddings") -> int:
    """
    Store PDF embeddings using the unified vector store.
    
    Args:
        chunks: List of text chunks with metadata
        table_name: Supabase table name for PDF embeddings
        
    Returns:
        Number of embeddings stored
    """
    if not chunks:
        logger.warning("No chunks provided for PDF embedding storage")
        return 0
    
    # Use the unified storage function
    return store_embeddings_directly(chunks, table_name)

def check_duplicate_pdf(pdf_id: str, table_name: str = "pdf_embeddings") -> bool:
    """Check if PDF embeddings already exist for a given PDF ID."""
    from app.database.supabase import get_supabase
    try:
        supabase_client = get_supabase()
        result = supabase_client.table(table_name).select("id").eq("pdf_id", pdf_id).limit(1).execute()
        return len(result.data) > 0 if result.data else False
    except Exception as e:
        logger.error(f"Failed to check duplicate PDF {pdf_id}: {e}")
        return False

def delete_pdf_embeddings(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """Delete all embeddings for a specific PDF."""
    from app.database.supabase import get_supabase
    try:
        supabase_client = get_supabase()
        result = supabase_client.table(table_name).delete().eq("pdf_id", pdf_id).execute()
        deleted_count = len(result.data) if result.data else 0
        logger.info(f"Deleted {deleted_count} embeddings for PDF {pdf_id}")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to delete PDF embeddings for {pdf_id}: {e}")
        return 0

def get_pdf_embeddings_count(pdf_id: str, table_name: str = "pdf_embeddings") -> int:
    """Get the number of embeddings for a specific PDF."""
    from app.database.supabase import get_supabase
    try:
        supabase_client = get_supabase()
        result = supabase_client.table(table_name).select("id", count="exact").eq("pdf_id", pdf_id).execute()
        return result.count if result.count else 0
    except Exception as e:
        logger.error(f"Failed to count PDF embeddings for {pdf_id}: {e}")
        return 0

def list_pdf_documents(table_name: str = "pdf_embeddings") -> List[Dict[str, Any]]:
    """List all PDF documents that have embeddings stored."""
    from app.database.supabase import get_supabase
    try:
        supabase_client = get_supabase()
        result = supabase_client.table(table_name).select(
            "pdf_id, pdf_title, created_at"
        ).order("created_at", desc=True).execute()
        
        if not result.data:
            return []
        
        # Group by PDF ID
        pdf_docs = {}
        for row in result.data:
            pdf_id = row.get("pdf_id")
            if pdf_id not in pdf_docs:
                pdf_docs[pdf_id] = {
                    "pdf_id": pdf_id,
                    "pdf_title": row.get("pdf_title", "Unknown"),
                    "created_at": row.get("created_at"),
                    "embedding_count": 0
                }
            pdf_docs[pdf_id]["embedding_count"] += 1
        
        return list(pdf_docs.values())
    except Exception as e:
        logger.error(f"Failed to list PDF documents: {e}")
        return []
