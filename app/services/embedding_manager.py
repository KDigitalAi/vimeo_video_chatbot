"""
Embedding manager for OpenAI embeddings.
"""
import os
from functools import lru_cache
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe, memory_guard

logger = get_logger_safe(__name__)


def _get_settings():
    """Lazy import of settings to prevent import-time failures."""
    return get_settings_safe()

# CRITICAL: Set environment variable lazily, not at module level
# This prevents crashes if settings aren't fully initialized
def _ensure_openai_key():
    """Set OpenAI API key in environment if available."""
    try:
        settings = _get_settings()
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    except Exception:
        # Silently fail - will be set when embeddings are actually needed
        # Check environment variable as fallback
        if not os.environ.get("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key

# Lazy import to reduce memory footprint
def _get_openai_embeddings():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings

@lru_cache(maxsize=1)
def get_embeddings_instance():
    """
    Get OpenAI embeddings instance with proper API key configuration.
    Cached to reduce initialization overhead and memory usage.
    """
    # Get logger and settings lazily
    settings = _get_settings()
    
    # Ensure API key is set before proceeding
    _ensure_openai_key()
    
    # Check memory before creating embeddings instance
    memory_guard(logger, "creating embeddings instance")
    
    # Double-check that the API key is available (try environment first, then settings)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = settings.OPENAI_API_KEY
        except (AttributeError, Exception):
            api_key = None
    
    if not api_key or not api_key.strip():
        raise ValueError("OPENAI_API_KEY not found in environment variables or settings. Please check your .env file.")
    
    # Ensure API key is set in environment for LangChain
    if api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key
        logger.info("OPENAI_API_KEY set in environment from settings")
    
    try:
        # Lazy load OpenAIEmbeddings
        OpenAIEmbeddings = _get_openai_embeddings()
        
        # Get embedding model from settings
        try:
            embedding_model = settings.EMBEDDING_MODEL
        except (AttributeError, Exception):
            embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        
        # Match DB / RPC vector(1536); prevents silent len mismatch in vector_store fallback
        try:
            embed_dims = int(getattr(settings, "EMBEDDING_DIMENSIONS", 1536))
        except (AttributeError, TypeError, ValueError):
            embed_dims = 1536

        emb_kwargs = dict(
            model=embedding_model,
            chunk_size=100,
            max_retries=3,
            request_timeout=30,
        )
        if embedding_model.startswith("text-embedding-3") and embed_dims:
            emb_kwargs["dimensions"] = embed_dims

        embeddings = OpenAIEmbeddings(**emb_kwargs)
        
        from app.utils.logger import log_memory_usage
        log_memory_usage("embeddings instance creation")
        return embeddings
        
    except Exception as e:
        logger.error(f"Failed to create embeddings instance: {e}")
        from app.utils.logger import cleanup_memory
        cleanup_memory()
        raise

