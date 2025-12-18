"""
Lightweight Supabase-backed vector store shim to satisfy chat.py expectations.
Provides a `load_supabase_vectorstore()` that returns an object with
`similarity_search_by_vector_with_relevance_scores` reading from
pdf_embeddings table (PDF-only mode).
"""
from typing import List, Tuple, Any
from app.utils.logger import logger


def _get_supabase():
    """Lazy import of Supabase client with error handling."""
    try:
        from app.database.supabase import get_supabase
        return get_supabase()
    except Exception as e:
        logger.error(f"Failed to get Supabase client: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        # Fallback simple implementation
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
    return []


class _SimpleDocument:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class SupabaseVectorStore:
    def __init__(self):
        try:
            self._supabase = _get_supabase()
        except Exception as e:
            logger.error(f"Failed to initialize SupabaseVectorStore: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Cannot initialize vector store: {str(e)}") from e

    def similarity_search_by_vector_with_relevance_scores(self, query_embedding: list, k: int = 5) -> List[Tuple[_SimpleDocument, float]]:
        results: List[Tuple[_SimpleDocument, float]] = []

        # Query PDFs with limit to prevent memory issues
        # Fetch more than k to account for filtering, but not all rows
        try:
            # Fetch up to k*3 rows to ensure we have enough after filtering
            # This prevents loading all embeddings into memory
            fetch_limit = min(k * 3, 1000)  # Cap at 1000 for safety
            pdf_rows = self._supabase.table("pdf_embeddings").select("*").limit(fetch_limit).execute().data or []
            for row in pdf_rows:
                emb = _parse_embedding(row.get("embedding"))
                if not emb or len(emb) != len(query_embedding):
                    continue
                score = _cosine_similarity(query_embedding, emb)
                doc = _SimpleDocument(
                    page_content=row.get("content", ""),
                    metadata={
                        "source_type": "pdf",
                        "pdf_id": row.get("pdf_id"),
                        "pdf_title": row.get("pdf_title"),
                        "page_number": row.get("page_number"),
                        "chunk_id": row.get("chunk_id"),
                    },
                )
                results.append((doc, score))
        except Exception as e:
            # Log error but don't crash - return empty results instead
            logger.error(f"Failed to query PDF embeddings: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")

        # Video embeddings query removed - PDF-only mode

        # Sort by relevance and trim to top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def as_retriever(self, search_kwargs: dict = None):
        """
        Create a retriever compatible with LangChain's ConversationalRetrievalChain.
        """
        if search_kwargs is None:
            search_kwargs = {"k": 5}
        
        try:
            from langchain_core.retrievers import BaseRetriever
            from langchain_core.documents import Document
            
            class SupabaseRetriever(BaseRetriever):
                vector_store: Any
                search_kwargs: dict
                
                def __init__(self, vector_store, search_kwargs):
                    super().__init__(vector_store=vector_store, search_kwargs=search_kwargs)
                
                def _get_relevant_documents(self, query: str):
                    # This method is called by LangChain's ConversationalRetrievalChain
                    # We need to generate embeddings for the query first
                    try:
                        from app.services.embedding_manager import get_embeddings_instance
                        embeddings = get_embeddings_instance()
                        query_embedding = embeddings.embed_query(query)
                        
                        # Use our similarity search method
                        docs_with_scores = self.vector_store.similarity_search_by_vector_with_relevance_scores(
                            query_embedding, k=self.search_kwargs.get("k", 5)
                        )
                        
                        # Convert our SimpleDocument to LangChain Document
                        langchain_docs = []
                        for doc, score in docs_with_scores:
                            langchain_doc = Document(
                                page_content=doc.page_content,
                                metadata=doc.metadata
                            )
                            langchain_docs.append(langchain_doc)
                        
                        return langchain_docs
                    except Exception as e:
                        logger.error(f"Error in retriever: {e}")
                        return []
            
            return SupabaseRetriever(self, search_kwargs)
        except ImportError:
            # Fallback for older LangChain versions
            class SupabaseRetriever:
                def __init__(self, vector_store, search_kwargs):
                    self.vector_store = vector_store
                    self.search_kwargs = search_kwargs
                
                def get_relevant_documents(self, query: str):
                    try:
                        from app.services.embedding_manager import get_embeddings_instance
                        embeddings = get_embeddings_instance()
                        query_embedding = embeddings.embed_query(query)
                        
                        docs_with_scores = self.vector_store.similarity_search_by_vector_with_relevance_scores(
                            query_embedding, k=self.search_kwargs.get("k", 5)
                        )
                        
                        return [doc for doc, score in docs_with_scores]
                    except Exception as e:
                        logger.error(f"Error in retriever: {e}")
                        return []
            
            return SupabaseRetriever(self, search_kwargs)


def load_supabase_vectorstore() -> SupabaseVectorStore:
    return SupabaseVectorStore()


