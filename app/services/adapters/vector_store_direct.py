"""Direct PostgREST client adapter export."""
from app.services.vector_store_direct import get_supabase_direct, store_embeddings_directly

__all__ = ["get_supabase_direct", "store_embeddings_directly"]
