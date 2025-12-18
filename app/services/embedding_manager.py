"""
Embedding manager for OpenAI embeddings.
"""
import os
from functools import lru_cache

# Lazy imports to prevent module-level execution failures
def _get_settings():
    """Lazy import of settings to prevent import-time failures."""
    try:
        from app.config.settings import settings
        return settings
    except Exception as e:
        import logging
        logging.error(f"Failed to import settings in embedding_manager: {e}")
        # Fallback to environment variables only for critical settings
        import os
        class FallbackSettings:
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
            EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        return FallbackSettings()

def _get_logger():
    """Lazy import of logger to prevent import-time failures."""
    try:
        from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold
        return logger, log_memory_usage, cleanup_memory, check_memory_threshold
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
        def noop(*args, **kwargs):
            pass
        return logger, noop, noop, lambda *args: True

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
    logger, log_memory_usage, cleanup_memory, check_memory_threshold = _get_logger()
    settings = _get_settings()
    
    # Ensure API key is set before proceeding
    _ensure_openai_key()
    
    # Check memory before creating embeddings instance
    if not check_memory_threshold():
        logger.warning("Memory usage high before creating embeddings instance")
        cleanup_memory()
    
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
        
        # Create embeddings instance with memory optimization
        embeddings = OpenAIEmbeddings(
            model=embedding_model,
            chunk_size=100,  # Process embeddings in smaller chunks
            max_retries=3,   # Add retry logic
            request_timeout=30  # Add timeout
        )
        
        log_memory_usage("embeddings instance creation")
        return embeddings
        
    except Exception as e:
        logger.error(f"Failed to create embeddings instance: {e}")
        cleanup_memory()
        raise

