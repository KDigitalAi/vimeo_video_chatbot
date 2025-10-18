# backend/modules/embedding_manager.py
import os
from backend.core.settings import settings

# CRITICAL: Set environment variable BEFORE importing LangChain modules
# This ensures LangChain can find the API key when it initializes
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

# Import LangChain modules after setting environment variable
from langchain_openai import OpenAIEmbeddings

def get_embeddings_instance():
    """Get OpenAI embeddings instance with proper API key configuration."""
    # Double-check that the API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your .env file.")
    
    # LangChain wrapper - will read OPENAI_API_KEY from env
    return OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)

# if __name__ == "__main__":
#     try:
#         emb = get_embeddings_instance()
#         print(" Embedding model loaded successfully:", emb)
#     except Exception as e:
#         print("  Skipping API call (no valid OpenAI key). Code structure is working fine.")
#         print("Error details:", e)


