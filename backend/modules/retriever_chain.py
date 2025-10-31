# backend/modules/retriever_chain.py
from functools import lru_cache
from backend.core.settings import settings
from backend.modules.utils import logger, log_memory_usage, cleanup_memory, check_memory_threshold

# Lazy imports to reduce memory footprint
def _get_langchain_imports():
    """Get all required LangChain imports in one function."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain.chains import ConversationalRetrievalChain
        from langchain.memory import ConversationBufferMemory
        return ChatOpenAI, ConversationalRetrievalChain, ConversationBufferMemory
    except ImportError as e:
        logger.error(f"Failed to import LangChain modules: {e}")
        raise

def get_conversational_chain(vector_store, temperature: float = 0.0, k: int = 3):
    """
    Create conversational chain for a specific session.
    Each call creates a new chain with its own memory to ensure session isolation.
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before creating conversational chain")
        cleanup_memory()
    
    logger.info("Creating LLM and conversational chain using model %s", settings.LLM_MODEL)
    
    try:
        # Lazy load components
        ChatOpenAI, ConversationalRetrievalChain, ConversationBufferMemory = _get_langchain_imports()
        
        # Create LLM with memory optimization
        llm = ChatOpenAI(
            model=settings.LLM_MODEL, 
            temperature=temperature,
            max_tokens=1000,  # Limit response length to save memory
            request_timeout=30  # Add timeout to prevent hanging
        )
        
        # Create memory with size limits
        memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True,
            output_key="answer",
            max_token_limit=2000  # Limit memory size
        )
        
        # Create retriever with optimized search
        retriever = vector_store.as_retriever(
            search_kwargs={"k": min(k, 5)}  # Limit to 5 results max
        )
        
        # Create chain
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=True,
            output_key="answer",
            max_tokens_limit=1000,  # Limit total tokens
            verbose=False  # Reduce logging overhead
        )
        
        log_memory_usage("conversational chain creation")
        return chain
        
    except Exception as e:
        logger.error(f"Failed to create conversational chain: {e}")
        cleanup_memory()
        raise