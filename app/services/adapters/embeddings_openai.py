"""OpenAI embeddings adapter export."""
from app.services.embedding_manager import OpenAIEmbeddingsService, get_embeddings_service

__all__ = ["OpenAIEmbeddingsService", "get_embeddings_service"]
