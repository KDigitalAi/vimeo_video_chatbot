# backend/modules/embedding_manager.py
import os
from functools import lru_cache
from backend.core.settings import settings
from backend.modules.utils import logger, log_memory_usage, cleanup_memory, check_memory_threshold

# CRITICAL: Set environment variable BEFORE importing LangChain modules
# This ensures LangChain can find the API key when it initializes
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

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
    # Check memory before creating embeddings instance
    if not check_memory_threshold():
        logger.warning("Memory usage high before creating embeddings instance")
        cleanup_memory()
    
    # Double-check that the API key is available (try settings first, then environment)
    api_key = os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY
    if not api_key or not api_key.strip():
        raise ValueError("OPENAI_API_KEY not found in environment variables or settings. Please check your .env file.")
    
    # Ensure API key is set in environment for LangChain
    if api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key
        logger.info("OPENAI_API_KEY set in environment from settings")
    
    try:
        # Lazy load OpenAIEmbeddings
        OpenAIEmbeddings = _get_openai_embeddings()
        
        # Create embeddings instance with memory optimization
        embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
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

