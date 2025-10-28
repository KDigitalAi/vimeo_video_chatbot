# backend/routers/chat.py
"""
Chat router with enhanced security and validation.
Implements JWT authentication and comprehensive input validation.
Optimized for memory efficiency and performance.
"""
import time
import uuid
import gc
import random
from functools import lru_cache
from fastapi import APIRouter, HTTPException, status, Body, Request
from backend.modules.vector_store_direct import get_supabase_direct
from backend.modules.chat_history_manager import (
    store_chat_interaction, 
    get_chat_history, 
    get_chat_sessions,
    delete_chat_session,
    clear_all_chat_history
)
from backend.modules.utils import logger, log_memory_usage, cleanup_memory, check_memory_threshold
from backend.modules.embedding_manager import get_embeddings_instance
from backend.core.validation import ChatRequest, ChatResponse
from backend.core.settings import settings
from backend.core.security import get_current_user, HTTPAuthorizationCredentials

# Lazy imports for optional dependencies
try:
    from langchain.schema import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Import conversational chain for memory functionality
from backend.modules.retriever_chain import get_conversational_chain
from backend.modules.vector_store_direct import get_supabase_direct

router = APIRouter()

# Cache for LLM instances to avoid repeated initialization
_llm_cache = {}

def _get_llm_instance(model: str = None, temperature: float = 0.1):
    """Get cached LLM instance to avoid repeated initialization."""
    if model is None:
        model = settings.LLM_MODEL
    
    cache_key = f"{model}_{temperature}"
    if cache_key not in _llm_cache:
        try:
            from langchain_openai import ChatOpenAI
            _llm_cache[cache_key] = ChatOpenAI(model=model, temperature=temperature)
            logger.info(f"Created new LLM instance for {cache_key}")
        except Exception as e:
            logger.error(f"Failed to create LLM instance: {e}")
            raise
    
    return _llm_cache[cache_key]

def clear_llm_cache():
    """Clear the LLM cache to free memory."""
    global _llm_cache
    _llm_cache.clear()
    gc.collect()
    logger.info("LLM cache cleared")

def _calculate_average_similarity_score(docs_with_scores: list) -> float:
    """
    Calculate the average similarity score from retrieved documents.
    
    Args:
        docs_with_scores: List of (document, score) tuples
        
    Returns:
        Average similarity score, or 0.0 if no documents
    """
    if not docs_with_scores:
        return 0.0
    
    total_score = sum(score for _, score in docs_with_scores)
    return total_score / len(docs_with_scores)

def _create_vector_store_for_chain():
    """
    Create a LangChain-compatible vector store for the conversational chain.
    This wraps our Supabase direct client to work with LangChain's ConversationalRetrievalChain.
    """
    try:
        from langchain.vectorstores import VectorStore
        from langchain.schema import Document
        from backend.modules.embedding_manager import get_embeddings_instance
        import numpy as np
        
        class SupabaseVectorStore(VectorStore):
            def __init__(self, supabase_client, embeddings):
                super().__init__()
                self.supabase_client = supabase_client
                self._embeddings = embeddings
            
            @property
            def embeddings(self):
                """Return the embeddings instance."""
                return self._embeddings
            
            def similarity_search(self, query, k=5, **kwargs):
                """Perform similarity search using our existing search logic."""
                try:
                    # Get query embedding
                    query_embedding = self._embeddings.embed_query(query)
                    
                    # Use our existing search logic
                    docs_with_scores = _perform_unified_search(query_embedding, k)
                    
                    # Convert to LangChain Document format
                    documents = []
                    for doc, score in docs_with_scores:
                        documents.append(Document(
                            page_content=doc.page_content,
                            metadata=doc.metadata
                        ))
                    
                    return documents
                except Exception as e:
                    logger.error(f"Error in similarity search: {e}")
                    return []
            
            def as_retriever(self, search_kwargs=None):
                """Return a retriever for this vector store."""
                from langchain.vectorstores.base import VectorStoreRetriever
                
                if search_kwargs is None:
                    search_kwargs = {}
                
                return VectorStoreRetriever(
                    vectorstore=self,
                    search_type="similarity",
                    search_kwargs=search_kwargs
                )
            
            @classmethod
            def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
                """Required abstract method - not used in our implementation."""
                # This method is required by LangChain but not used in our case
                # since we're using existing embeddings from Supabase
                raise NotImplementedError("from_texts not implemented - using existing Supabase embeddings")
            
            def add_texts(self, texts, metadatas=None, **kwargs):
                """Required abstract method - not used in our implementation."""
                # This method is required by LangChain but not used in our case
                # since we're using existing embeddings from Supabase
                raise NotImplementedError("add_texts not implemented - using existing Supabase embeddings")
        
        # Create the vector store
        supabase_client = get_supabase_direct()
        embeddings = get_embeddings_instance()
        
        return SupabaseVectorStore(supabase_client, embeddings)
        
    except Exception as e:
        logger.error(f"Error creating vector store for chain: {e}")
        raise

def _seed_chain_memory_from_history(chain, user_id: str, session_id: str, limit: int = 10) -> None:
    """
    Load recent chat history from DB and seed into chain.memory as LangChain messages.
    Keeps order oldest → newest for proper conversation flow.
    
    Args:
        chain: ConversationalRetrievalChain instance
        user_id: User identifier
        session_id: Session identifier
        limit: Maximum number of conversation turns to load
    """
    try:
        # Get chat history from database (newest first)
        history = get_chat_history(user_id=user_id, session_id=session_id, limit=limit)
        
        logger.info(f"DIAGNOSTIC: Retrieved {len(history)} history items from DB for session {session_id}")
        
        if not history:
            logger.info("No chat history found for session, starting fresh conversation")
            return
        
        # DIAGNOSTIC: Log history items
        for i, item in enumerate(history):
            logger.info(f"DIAGNOSTIC: History item {i}: user='{item.get('user_message', '')[:50]}...', bot='{item.get('bot_response', '')[:50]}...'")
        
        # Reverse to get oldest → newest order for memory
        messages_added = 0
        for item in reversed(history):
            user_msg = item.get("user_message")
            bot_msg = item.get("bot_response")
            
            # Add user message to memory
            if user_msg:
                chain.memory.chat_memory.add_message(HumanMessage(content=user_msg))
                messages_added += 1
                logger.info(f"DIAGNOSTIC: Added user message to memory: '{user_msg[:50]}...'")
            
            # Add bot response to memory
            if bot_msg:
                chain.memory.chat_memory.add_message(AIMessage(content=bot_msg))
                messages_added += 1
                logger.info(f"DIAGNOSTIC: Added bot message to memory: '{bot_msg[:50]}...'")
        
        logger.info(f"DIAGNOSTIC: Seeded chain memory with {messages_added} messages from {len(history)} conversation turns")
        
    except Exception as e:
        logger.warning(f"Unable to seed memory from history: {e}")
        # Continue without memory seeding

def _perform_unified_search(query_embedding: list, top_k: int = 5) -> list:
    """
    Perform unified search across both video and PDF embeddings.
    Optimized for memory efficiency and performance.
    
    Args:
        query_embedding: Query embedding vector
        top_k: Number of results to return
        
    Returns:
        List of (document, score) tuples
    """
    try:
        import numpy as np
        from backend.core.supabase_client import get_supabase
        
        supabase_client = get_supabase()
        docs_with_scores = []
        
        # Search PDF embeddings
        try:
            pdf_result = supabase_client.table('pdf_embeddings').select('*').execute()
            
            if pdf_result.data:
                for row in pdf_result.data:
                    # Calculate cosine similarity
                    embedding_str = row['embedding']
                    if embedding_str:
                        try:
                            # Parse the embedding string (it's stored as a string representation of a list)
                            if isinstance(embedding_str, str):
                                # Remove brackets and split by comma, then convert to float
                                embedding_str = embedding_str.strip('[]')
                                embedding = [float(x.strip()) for x in embedding_str.split(',')]
                            else:
                                embedding = embedding_str
                            
                            if len(embedding) == len(query_embedding):
                                # Convert to numpy arrays for efficient calculation
                                query_vec = np.array(query_embedding)
                                doc_vec = np.array(embedding)
                                
                                # Calculate cosine similarity
                                dot_product = np.dot(query_vec, doc_vec)
                                norm_query = np.linalg.norm(query_vec)
                                norm_doc = np.linalg.norm(doc_vec)
                                
                                if norm_query > 0 and norm_doc > 0:
                                    similarity = dot_product / (norm_query * norm_doc)
                                    
                                    # Create document object
                                    doc = type('Document', (), {
                                        'page_content': row['content'],
                                        'metadata': {
                                            'video_id': None,
                                            'video_title': None,
                                            'chunk_id': row.get('chunk_id'),
                                            'timestamp_start': None,
                                            'timestamp_end': None,
                                            'source_type': 'pdf',
                                            'page_number': row.get('page_number'),
                                            'pdf_id': row.get('pdf_id'),
                                            'pdf_title': row.get('pdf_title')
                                        }
                                    })()
                                    docs_with_scores.append((doc, float(similarity)))
                        except Exception as e:
                            logger.debug(f"Error processing PDF embedding: {e}")
                            continue
        except Exception as e:
            logger.warning(f"PDF search failed: {e}")
        
        # Search video embeddings
        try:
            video_result = supabase_client.table('video_embeddings').select('*').execute()
            
            if video_result.data:
                for row in video_result.data:
                    # Calculate cosine similarity
                    embedding_str = row['embedding']
                    if embedding_str:
                        try:
                            # Parse the embedding string (it's stored as a string representation of a list)
                            if isinstance(embedding_str, str):
                                # Remove brackets and split by comma, then convert to float
                                embedding_str = embedding_str.strip('[]')
                                embedding = [float(x.strip()) for x in embedding_str.split(',')]
                            else:
                                embedding = embedding_str
                            
                            if len(embedding) == len(query_embedding):
                                # Convert to numpy arrays for efficient calculation
                                query_vec = np.array(query_embedding)
                                doc_vec = np.array(embedding)
                                
                                # Calculate cosine similarity
                                dot_product = np.dot(query_vec, doc_vec)
                                norm_query = np.linalg.norm(query_vec)
                                norm_doc = np.linalg.norm(doc_vec)
                                
                                if norm_query > 0 and norm_doc > 0:
                                    similarity = dot_product / (norm_query * norm_doc)
                                    
                                    # Create document object
                                    doc = type('Document', (), {
                                        'page_content': row['content'],
                                        'metadata': {
                                            'video_id': row.get('video_id'),
                                            'video_title': row.get('video_title'),
                                            'chunk_id': row.get('chunk_id'),
                                            'timestamp_start': row.get('timestamp_start'),
                                            'timestamp_end': row.get('timestamp_end'),
                                            'source_type': 'video',
                                            'page_number': None,
                                            'pdf_id': None,
                                            'pdf_title': None
                                        }
                                    })()
                                    docs_with_scores.append((doc, float(similarity)))
                        except Exception as e:
                            logger.debug(f"Error processing video embedding: {e}")
                            continue
        except Exception as e:
            logger.warning(f"Video search failed: {e}")
        
        # Sort by similarity score and return top_k results
        docs_with_scores.sort(key=lambda x: x[1], reverse=True)
        return docs_with_scores[:top_k]
        
    except Exception as e:
        logger.error(f"Unified search failed: {e}")
        return []

def _generate_unified_response(query: str, relevant_docs: list, is_partial_context: bool = False) -> str:
    """
    Generate response using both video and PDF content.
    Optimized for O(n) time complexity and reduced space complexity.
    """
    try:
        if not check_memory_threshold():
            cleanup_memory()
        
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is not available")
        
        # Build context from both video and PDF sources with intelligent merging
        context_parts = []
        max_context_length = 8000
        current_length = 0
        has_placeholder_content = False
        seen_content = set()  # Track content to avoid repetition
        
        for doc, score in relevant_docs:
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
            source_type = metadata.get("source_type", "unknown")
            source_title = metadata.get("video_title") or metadata.get("pdf_title", "Unknown")
            
            # Check for placeholder content patterns
            placeholder_patterns = [
                "this is a video about",
                "in this presentation, we'll cover",
                "let's start with an overview",
                "we'll discuss the important concepts",
                "the implementation details will be covered",
                "here are some examples to illustrate",
                "let's review what we've learned",
                "in conclusion, these are the main takeaways"
            ]
            
            content_lower = content.lower()
            # Be conservative: only treat as placeholder if very short and generic.
            # Never skip video content solely due to placeholder patterns.
            if source_type == "pdf":
                if len(content) < 200 and any(pattern in content_lower for pattern in placeholder_patterns):
                    has_placeholder_content = True
                    continue  # Skip only trivial PDF placeholders
            
            # Create content hash to avoid repetition
            content_hash = hash(content[:200])  # Use first 200 chars as hash
            if content_hash in seen_content:
                continue  # Skip duplicate content
            seen_content.add(content_hash)
            
            # Format based on source type with clear source attribution
            if source_type == "video":
                timestamp = f"{metadata.get('timestamp_start', '')} - {metadata.get('timestamp_end', '')}"
                context_part = f"**Video Source:** '{source_title}' ({timestamp})\n{content}"
            elif source_type == "pdf":
                page_num = metadata.get("page_number", "")
                page_info = f" (Page {page_num})" if page_num else ""
                context_part = f"**PDF Source:** '{source_title}'{page_info}\n{content}"
            else:
                context_part = f"**Source:** '{source_title}'\n{content}"
            
            # Truncate content efficiently while preserving meaning
            if len(content) > 1000:
                # Try to truncate at sentence boundary
                truncated = content[:1000]
                last_period = truncated.rfind('.')
                if last_period > 800:  # Only if we have a reasonable sentence
                    content = truncated[:last_period + 1] + "..."
                else:
                    content = truncated + "..."
            
            context_part = context_part.replace(content, content)  # Update with truncated content
            
            if current_length + len(context_part) > max_context_length:
                break
                
            context_parts.append(context_part)
            current_length += len(context_part) + 2  # +2 for "\n\n"
        
        context = "\n\n".join(context_parts)

        # If no usable context was assembled, do not call LLM
        if not context_parts:
            return "Sorry, I couldn't find relevant information in your uploaded videos or PDFs. Please check your materials and try again."
        
        # Handle case when only placeholder content was found
        if has_placeholder_content and not context_parts:
            # Strict restriction: do not use general-knowledge LLM fallback
            return "Sorry, I couldn't find relevant information in your uploaded videos or PDFs. Please check your materials and try again."
        
        # Enhanced system prompt for educational clarity, strict grounding, and structure
        system_prompt = """You are a helpful educational assistant. Answer ONLY using the provided context extracted from the user's Vimeo videos and PDFs.

STRICT GROUNDING RULES:
1. Do NOT use outside knowledge. If the context is insufficient, clearly say it is insufficient.
2. Never invent facts or details not present in the context.
3. Attribute sources when possible: include video titles and timestamps, or PDF titles and page numbers.

EDUCATIONAL STYLE:
1. Use a simple, student-friendly academic tone.
2. Prefer short sentences and clear wording. Avoid unnecessary jargon.
3. Add these section headers and keep them brief:
   - **📘 Definition**
   - **💡 Example**
   - **🎯 Key Points**
   - **📝 Note**
   - **🔍 Why It Matters**

FORMATTING:
1. Use markdown. Insert blank lines between sections for readability.
2. Use bullet points for lists. Bold key terms.

MERGING MULTIPLE SOURCES:
1. Combine overlapping information without repeating.
2. If sources disagree or are incomplete, say so briefly.

INSUFFICIENT CONTEXT:
1. If the provided context is too short or vague, state: "The available video/PDF context is insufficient to answer fully."

Provided Context:
{context}"""

        # Use cached LLM instance - O(1) time complexity
        llm = _get_llm_instance(temperature=0.1)
        
        # Generate response with minimal object creation
        response = llm.invoke([
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ])
        
        # Add partial context note if applicable
        if is_partial_context:
            return f"{response.content}\n\n*Note: This response is based on limited information from skill capital institute uploaded materials.*"
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating unified response: {e}")
        cleanup_memory()
        return "I found relevant content but encountered an error processing it. Please try rephrasing your question."

def _generate_video_based_response(query: str, relevant_docs: list, is_partial_context: bool = False) -> str:
    """
    Generate a response based only on video content using LLM.
    Optimized for O(n) time complexity and reduced space complexity.
    """
    try:
        if not check_memory_threshold():
            cleanup_memory()
        
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is not available")
        
        # Optimized context building with single pass - O(n) time complexity
        context_parts = []
        max_context_length = 8000
        current_length = 0
        
        for doc, score in relevant_docs:
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
            video_title = metadata.get("video_title", "Unknown Video")
            timestamp = f"{metadata.get('timestamp_start', '')} - {metadata.get('timestamp_end', '')}"
            
            # Truncate content efficiently
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            # Build context part and check length in one operation
            context_part = f"From '{video_title}' ({timestamp}): {content}"
            if current_length + len(context_part) > max_context_length:
                break
                
            context_parts.append(context_part)
            current_length += len(context_part) + 2  # +2 for "\n\n"
        
        # Use join for O(n) string concatenation instead of repeated concatenation
        context = "\n\n".join(context_parts)
        
        # Enhanced system prompt for video-based educational responses
        system_prompt = """You are a helpful educational assistant that provides clear, structured answers based ONLY on the provided video content.

EDUCATIONAL FORMATTING RULES:
1. Always structure your response with clear educational sections:
   - **📘 Definition:** for clear definitions and explanations
   - **💡 Examples:** for practical examples and demonstrations
   - **🎯 Key Points:** for important concepts and takeaways
   - **📝 Note:** for additional context or important reminders
   - **🔍 Why It Matters:** for explaining importance and relevance

2. FORMATTING GUIDELINES:
   - Use bullet points (- or *) for lists
   - Use **bold text** for key terms and important concepts
   - Keep sentences short and clear (under 20 words when possible)
   - Add blank lines between sections for readability
   - Use numbered lists for step-by-step processes

3. CONTENT RULES:
   - Answer ONLY using information from the provided video content below
   - Do NOT add any information not present in the video content
   - If the video content doesn't contain enough information, say so clearly
   - Focus on accuracy and learning
   - Use simple, educational language appropriate for students

4. RESPONSE STRUCTURE:
   - Start with a clear definition or overview
   - Provide practical examples from the video
   - Highlight key points mentioned in the video
   - Add relevant notes or context
   - Keep the tone helpful and encouraging

Video Content:
{context}"""

        # Use cached LLM instance - O(1) time complexity
        llm = _get_llm_instance(temperature=0.1)
        
        # Generate response with minimal object creation
        response = llm.invoke([
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ])
        
        # Add partial context note if applicable
        if is_partial_context:
            return f"{response.content}\n\n*Note: This response is based on limited information from your uploaded materials. For more comprehensive information, please check your video and PDF content.*"
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating video-based response: {e}")
        cleanup_memory()
        return "I found relevant video content but encountered an error processing it. Please try rephrasing your question."


def _generate_clarification_response(query: str, relevant_docs: list, is_partial_context: bool = False) -> str:
    """
    Generate a clarification response by rephrasing existing video content for better understanding.
    Optimized for O(n) time complexity and reduced space complexity.
    """
    try:
        if not check_memory_threshold():
            cleanup_memory()
        
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is not available")
        
        # Optimized context building with single pass - O(n) time complexity
        context_parts = []
        max_context_length = 8000
        current_length = 0
        
        for doc, score in relevant_docs:
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
            video_title = metadata.get("video_title", "Unknown Video")
            timestamp = f"{metadata.get('timestamp_start', '')} - {metadata.get('timestamp_end', '')}"
            
            # Truncate content efficiently
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            # Build context part and check length in one operation
            context_part = f"From '{video_title}' ({timestamp}): {content}"
            if current_length + len(context_part) > max_context_length:
                break
                
            context_parts.append(context_part)
            current_length += len(context_part) + 2  # +2 for "\n\n"
        
        # Use join for O(n) string concatenation
        context = "\n\n".join(context_parts)

        # If no usable context is available, do not call LLM
        if not context_parts:
            return "Sorry, I couldn't find relevant information in your uploaded videos or PDFs. Please check your materials and try again."
        
        # Enhanced system prompt for clarification with strict grounding and student-friendly tone
        system_prompt = """You are a helpful educational assistant. Rephrase and simplify ONLY the provided context from the user's videos.

STRICT GROUNDING:
1. Do NOT introduce any information not present in the context.
2. If the context is incomplete, say so briefly and stay within what is given.
3. Attribute sources (video title and timestamps) when possible.

EDUCATIONAL STYLE:
1. Use short, clear sentences and simple wording.
2. Use these section headers with brief content:
   - **📘 Definition**
   - **💡 Example**
   - **🎯 Key Points**
   - **📝 Note**
   - **🔍 Why It Matters**

FORMATTING:
1. Markdown with blank lines between sections.
2. Bullet points for lists; bold key terms.

INSUFFICIENT CONTEXT:
1. If details are missing, say: "The available video context is insufficient for a complete answer."

Video Context:
{context}"""

        # Use cached LLM instance - O(1) time complexity
        llm = _get_llm_instance(temperature=0.2)
        
        # Generate response with minimal object creation
        response = llm.invoke([
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ])
        
        # Add partial context note if applicable
        if is_partial_context:
            return f"{response.content}\n\n*Note: This response is based on limited information from your uploaded materials. For more comprehensive information, please check your video and PDF content.*"
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating clarification response: {e}")
        cleanup_memory()
        return "I found relevant video content but encountered an error explaining it. Please try rephrasing your question."

@router.post("/query", response_model=ChatResponse)
async def query_chat(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = None
):
    """
    Process chat request.query with enhanced security and validation.
    Optimized for memory efficiency and performance.
    
    Args:
        request: Validated chat request
        credentials: JWT authentication credentials (optional)
        
    Returns:
        ChatResponse with answer and sources
        
    Raises:
        HTTPException: For various error conditions
    """
    # Detailed request logging
    logger.info("=== INCOMING CHAT REQUEST ===")
    logger.info(f"Query: {request.query}")
    logger.info(f"User ID: {request.user_id}")
    logger.info(f"Conversation ID: {request.conversation_id}")
    logger.info(f"Include Sources: {request.include_sources}")
    logger.info(f"Top K: {request.top_k}")
    logger.info("=== END REQUEST LOGGING ===")
    start_time = time.time()
    
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before processing request.query")
        cleanup_memory()
    
    try:
        
        # Optimized greeting detection - O(1) average case with early termination
        # Use frozenset for O(1) lookup performance
        greeting_keywords = frozenset({'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings', 'howdy'})
        query_lower = request.query.lower().strip()
        
        # O(1) lookup for exact matches, O(k) for prefix matches where k is keyword length
        # Use set intersection for faster prefix matching
        is_greeting = (query_lower in greeting_keywords or 
                      any(query_lower.startswith(keyword + ' ') for keyword in greeting_keywords))
        
        if is_greeting:
            # Optimized greeting responses with single random selection
            greeting_responses = [
                "Hello! I'm your Vimeo Video Chatbot. I can help you find information from your Vimeo videos. What would you like to know?",
                "Hi there! I'm here to help you explore your Vimeo video content. Feel free to ask me any questions about your videos!",
                "Hello! Welcome to your Vimeo Video Chatbot. I can search through your video content and answer questions about what's covered in your videos.",
                "Hey! I'm your AI assistant for Vimeo videos. Ask me anything about the content in your video library!"
            ]
            answer = random.choice(greeting_responses)
            
            # Store the greeting interaction
            try:
                session_id = request.conversation_id or str(uuid.uuid4())
                chat_id = store_chat_interaction(
                    user_id=request.user_id or "anonymous",
                    session_id=session_id,
                    user_message=request.query,
                    bot_response=answer,
                    video_id=None
                )
                logger.info(f"Greeting interaction stored with ID: {chat_id}")
            except Exception as e:
                logger.error(f"Error storing greeting interaction: {e}")
            
            return ChatResponse(
                answer=answer,
                sources=[],
                conversation_id=session_id,
                processing_time=0.1,
                timestamp=time.time()
            )

        # Perform unified similarity search across videos and PDFs
        try:
            logger.info("Performing unified similarity search for query: %s", request.query)
            
            # Generate embedding for the query (cached)
            embeddings = get_embeddings_instance()  # This is already cached
            query_embedding = embeddings.embed_query(request.query)
            
            # Perform unified search (videos + PDFs)
            docs_with_scores = _perform_unified_search(query_embedding, request.top_k)
            
            logger.info("Found %d relevant documents", len(docs_with_scores))
            log_memory_usage("similarity search completed")
            
            # Similarity thresholds for restricted responses
            HIGH_CONFIDENCE_THRESHOLD = 0.5
            LOW_CONFIDENCE_THRESHOLD = 0.3
            MINIMUM_THRESHOLD = 0.2
            
            # Calculate average similarity score for threshold decisions
            avg_similarity_score = _calculate_average_similarity_score(docs_with_scores)
            logger.info(f"Average similarity score: {avg_similarity_score:.3f}")
            
            # Define session_id early for potential early returns
            session_id = request.conversation_id or str(uuid.uuid4())
            user_id = request.user_id or "anonymous"
            
            # Check if we have any relevant content at all
            if not docs_with_scores or avg_similarity_score < MINIMUM_THRESHOLD:
                logger.info("No relevant content found in videos or PDFs")
                answer = "Sorry, I couldn't find relevant information in your uploaded videos or PDFs. Please check your materials and try again."
                sources = []
                
                # Store the interaction and return early
                try:
                    chat_id = store_chat_interaction(
                        user_id=user_id,
                        session_id=session_id,
                        user_message=request.query,
                        bot_response=answer,
                        video_id=None
                    )
                    logger.info(f"No-content interaction stored with ID: {chat_id}")
                except Exception as e:
                    logger.error(f"Error storing no-content interaction: {e}")
                
                return ChatResponse(
                    answer=answer,
                    sources=sources,
                    conversation_id=session_id,
                    processing_time=time.time() - start_time,
                    timestamp=time.time()
                )
            else:
                # We have some relevant content - categorize by confidence
                relevant_docs = []
                low_confidence_docs = []
                best_score = 0.0
                best_doc = None
                
                # Single pass through documents with early termination
                for doc, score in docs_with_scores:
                    # Log first 5 scores for debugging
                    if len(relevant_docs) + len(low_confidence_docs) < 5:
                        logger.info("Document similarity score: %.3f", score)
                    
                    if score >= HIGH_CONFIDENCE_THRESHOLD:
                        relevant_docs.append((doc, score))
                    elif score >= LOW_CONFIDENCE_THRESHOLD:
                        low_confidence_docs.append((doc, score))
                    
                    # Track best score for fallback
                    if score > best_score:
                        best_score = score
                        best_doc = (doc, score)
                
                # Use the best available documents
                if relevant_docs:
                    logger.info(f"Found {len(relevant_docs)} high confidence documents")
                    final_docs = relevant_docs
                elif low_confidence_docs:
                    logger.info(f"Found {len(low_confidence_docs)} low confidence documents - using for partial context")
                    final_docs = low_confidence_docs
                else:
                    logger.info(f"Using best available match with score {best_score:.3f}")
                    final_docs = [best_doc] if best_doc else []
                
                # Set relevant_docs for the rest of the processing
                relevant_docs = final_docs
                
                logger.info("Found %d relevant documents above threshold", len(relevant_docs))
                
                # Check confidence level of the best match
                best_score = max(score for _, score in relevant_docs)
                is_low_confidence = best_score < HIGH_CONFIDENCE_THRESHOLD
                is_partial_context = best_score < HIGH_CONFIDENCE_THRESHOLD and best_score >= LOW_CONFIDENCE_THRESHOLD
                
                if is_low_confidence:
                    logger.info(f"Low confidence response (score: {best_score:.3f})")
                if is_partial_context:
                    logger.info(f"Using partial context with LLM fallback (score: {best_score:.3f})")
                
                # Optimized clarification detection - O(k) where k is number of keywords
                clarification_keywords = {
                    'explain clearly', 'explain in simple terms', 'can you explain', 
                    'clarify', 'simplify', 'break down', 'elaborate', 'rephrase',
                    'what does this mean', 'help me understand', 'give more details',
                    'explain more', 'tell me more', 'expand on', 'go into detail',
                    'in more detail', 'more information', 'further explanation'
                }
                query_lower = request.query.lower()
                
                # O(k) keyword detection with early termination
                is_clarification_chat_data = any(keyword in query_lower for keyword in clarification_keywords)
                
                # Check if we have previous conversation history for memory
                
                # Check if this is a continuing conversation
                previous_history = get_chat_history(user_id=user_id, session_id=session_id, limit=1)
                
                if previous_history and len(previous_history) > 0:
                    # Use conversational chain with memory for continuity
                    logger.info("Using conversational chain with memory for continuing conversation")
                    logger.info(f"Found {len(previous_history)} previous messages in conversation {session_id}")
                    
                    try:
                        # Build vector store for retrieval
                        vector_store = _create_vector_store_for_chain()
                        
                        # Create conversational chain with memory
                        chain = get_conversational_chain(vector_store, temperature=0.1, k=request.top_k)
                        
                        # DIAGNOSTIC: Log memory state before seeding
                        logger.info(f"Memory before seeding: {len(chain.memory.chat_memory.messages)} messages")
                        logger.info(f"Memory buffer before: {chain.memory.buffer}")
                        
                        # Seed memory with previous conversation turns
                        _seed_chain_memory_from_history(chain, user_id, session_id, limit=10)
                        
                        # DIAGNOSTIC: Log memory state after seeding
                        logger.info(f"Memory after seeding: {len(chain.memory.chat_memory.messages)} messages")
                        logger.info(f"Memory buffer after: {chain.memory.buffer}")
                        
                        # Ask the chain with current question
                        chain_result = chain.invoke({"question": request.query})
                        
                        # Extract answer from chain result
                        answer = chain_result.get("answer") or ""
                        
                        # Extract source documents and convert to our format
                        source_docs = chain_result.get("source_documents") or []
                        sources = []
                        
                        if request.include_sources:
                            for doc in source_docs[:request.top_k]:
                                metadata = getattr(doc, "metadata", {})
                                source_type = metadata.get("source_type", "unknown")
                                
                                if source_type == "video":
                                    sources.append({
                                        "source_type": "video",
                                        "video_title": metadata.get("video_title"),
                                        "video_id": metadata.get("video_id"),
                                        "timestamp_start": metadata.get("timestamp_start"),
                                        "timestamp_end": metadata.get("timestamp_end"),
                                        "chunk_id": metadata.get("chunk_id"),
                                        "relevance_score": metadata.get("score", 0.0)
                                    })
                                elif source_type == "pdf":
                                    sources.append({
                                        "source_type": "pdf",
                                        "pdf_title": metadata.get("pdf_title"),
                                        "pdf_id": metadata.get("pdf_id"),
                                        "page_number": metadata.get("page_number"),
                                        "chunk_id": metadata.get("chunk_id"),
                                        "relevance_score": metadata.get("score", 0.0)
                                    })
                                else:
                                    sources.append({
                                        "source_type": source_type,
                                        "title": metadata.get("video_title") or metadata.get("pdf_title"),
                                        "chunk_id": metadata.get("chunk_id"),
                                        "relevance_score": metadata.get("score", 0.0)
                                    })
                        
                        logger.info("Successfully generated response using conversational chain with memory")
                        
                        # Handle fallback response marker
                        if answer.startswith("FALLBACK_RESPONSE:"):
                            answer = answer.replace("FALLBACK_RESPONSE: ", "")
                        
                    except Exception as e:
                        logger.error(f"Error using conversational chain: {e}")
                        # Fallback to original method
                        if is_clarification_chat_data and len(relevant_docs) > 0:
                            logger.info("Falling back to clarification response")
                            answer = _generate_clarification_response(request.query, relevant_docs, is_partial_context)
                        else:
                            logger.info("Falling back to unified response")
                            answer = _generate_unified_response(request.query, relevant_docs, is_partial_context)
                        
                        # Use original sources processing
                        sources = []
                        if request.include_sources:
                            for doc, score in relevant_docs:
                                md = getattr(doc, "metadata", None) or {}
                                source_type = md.get("source_type", "unknown")
                                
                                if source_type == "video":
                                    sources.append({
                                        "source_type": "video",
                                        "video_title": md.get("video_title"),
                                        "video_id": md.get("video_id"),
                                        "timestamp_start": md.get("timestamp_start"),
                                        "timestamp_end": md.get("timestamp_end"),
                                        "chunk_id": md.get("chunk_id"),
                                        "relevance_score": score
                                    })
                                elif source_type == "pdf":
                                    sources.append({
                                        "source_type": "pdf",
                                        "pdf_title": md.get("pdf_title"),
                                        "pdf_id": md.get("pdf_id"),
                                        "page_number": md.get("page_number"),
                                        "chunk_id": md.get("chunk_id"),
                                        "relevance_score": score
                                    })
                                else:
                                    sources.append({
                                        "source_type": source_type,
                                        "title": md.get("video_title") or md.get("pdf_title"),
                                        "chunk_id": md.get("chunk_id"),
                                        "relevance_score": score
                                    })

                else:
                    # First message in conversation - use original method without memory
                    logger.info("First message in conversation, using original response generation")
                    
                    if is_clarification_chat_data and len(relevant_docs) > 0:
                        logger.info("User requesting clarification - using LLM to rephrase video content")
                        answer = _generate_clarification_response(request.query, relevant_docs, is_partial_context)
                    else:
                        logger.info("Generating response based on unified content (videos + PDFs)")
                        answer = _generate_unified_response(request.query, relevant_docs, is_partial_context)
                    
                    # Handle fallback response marker
                    if answer.startswith("FALLBACK_RESPONSE:"):
                        answer = answer.replace("FALLBACK_RESPONSE: ", "")
                    
                    # Original sources processing
                    sources = []
                    if request.include_sources:
                        for doc, score in relevant_docs:
                            md = getattr(doc, "metadata", None) or {}
                            source_type = md.get("source_type", "unknown")
                            
                            if source_type == "video":
                                sources.append({
                                    "source_type": "video",
                                    "video_title": md.get("video_title"),
                                    "video_id": md.get("video_id"),
                                    "timestamp_start": md.get("timestamp_start"),
                                    "timestamp_end": md.get("timestamp_end"),
                                    "chunk_id": md.get("chunk_id"),
                                    "relevance_score": score
                                })
                            elif source_type == "pdf":
                                sources.append({
                                    "source_type": "pdf",
                                    "pdf_title": md.get("pdf_title"),
                                    "pdf_id": md.get("pdf_id"),
                                    "page_number": md.get("page_number"),
                                    "chunk_id": md.get("chunk_id"),
                                    "relevance_score": score
                                })
                            else:
                                sources.append({
                                    "source_type": source_type,
                                    "title": md.get("video_title") or md.get("pdf_title"),
                                    "chunk_id": md.get("chunk_id"),
                                    "relevance_score": score
                                })
            
        except Exception as e:
            logger.exception("Error during similarity search: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing request.query"
            )
        
        processing_time = time.time() - start_time
        
        # Optimized cleanup - only clean up variables that exist
        if 'docs_with_scores' in locals():
            del docs_with_scores
        if 'relevant_docs' in locals():
            del relevant_docs
        if 'low_confidence_docs' in locals():
            del low_confidence_docs
        gc.collect()
        log_memory_usage("request.query processing completed")
        
        # Store chat interaction in database
        try:
            # Use the session_id we already determined earlier
            # session_id is already set from the conversation logic above
            
            # Extract video_id from sources if available
            video_id = None
            if sources and len(sources) > 0:
                video_id = sources[0].get("video_id")
            
            # Store the chat interaction
            chat_id = store_chat_interaction(
                user_id=request.user_id or "anonymous",
                session_id=session_id,
                user_message=request.query,
                bot_response=answer,
                video_id=video_id
            )
            
            if chat_id:
                logger.info(f"Chat interaction stored with ID: {chat_id}")
            else:
                logger.warning("Failed to store chat interaction")
            
            # Store user query in user_queries table
            try:
                from backend.core.supabase_client import get_supabase
                
                # Generate embedding for the user query
                embeddings = get_embeddings_instance()
                query_embedding = embeddings.embed_query(request.query)
                
                # Store in user_queries table
                supabase = get_supabase()
                query_record = {
                    "user_id": request.user_id or "anonymous",
                    "query_text": request.query,
                    "query_embedding": query_embedding,
                    "matched_video_id": video_id,
                    "matched_chunk_id": sources[0].get("chunk_id") if sources else None,
                    "matched_document_type": sources[0].get("source_type") if sources else None,
                    "matched_pdf_id": sources[0].get("pdf_id") if sources else None,
                    "matched_page_number": sources[0].get("page_number") if sources else None
                }
                
                result = supabase.table("user_queries").insert(query_record).execute()
                if result.data:
                    logger.info(f"User query stored with ID: {result.data[0]['id']}")
                else:
                    logger.warning("Failed to store user query")
                    
            except Exception as e:
                logger.error(f"Error storing user query: {e}")
                # Don't fail the chat if user query storage fails
                
        except Exception as e:
            logger.error(f"Error storing chat interaction: {e}")
            # Don't fail the chat_data if chat history storage fails
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=session_id,
            processing_time=round(processing_time, 3),
            tokens_used=None  # Would be populated by LLM response
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in request.query_chat")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/history/{user_id}")
async def get_user_chat_history(
    user_id: str,
    session_id: str = None,
    limit: int = 50
):
    """
    Retrieve chat history for a user.
    Optimized for memory efficiency.
    
    Args:
        user_id: User identifier
        session_id: Optional session identifier to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records
    """
    try:
        # Limit the maximum number of records to prevent memory issues
        limit = min(limit, 100)  # Cap at 100 records
        
        history = get_chat_history(user_id, session_id, limit)
        log_memory_usage(f"chat history retrieved for {user_id}")
        
        return {
            "user_id": user_id,
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.exception("Error retrieving chat history")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat history"
        )


@router.get("/sessions/{user_id}")
async def get_user_chat_sessions(user_id: str):
    """
    Get all chat sessions for a user.
    Optimized for memory efficiency.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of chat sessions
    """
    try:
        sessions = get_chat_sessions(user_id)
        log_memory_usage(f"chat sessions retrieved for {user_id}")
        
        return {
            "user_id": user_id,
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.exception("Error retrieving chat sessions")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat sessions"
        )


@router.delete("/session/{user_id}/{session_id}")
async def delete_user_chat_session(user_id: str, session_id: str):
    """
    Delete a specific chat session.
    Optimized for memory efficiency.
    
    Args:
        user_id: User identifier
        session_id: Session identifier to delete
        
    Returns:
        Success message
    """
    try:
        success = delete_chat_session(user_id, session_id)
        if success:
            log_memory_usage(f"chat session deleted for {user_id}")
            return {"message": f"Chat session {session_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete chat session"
            )
    except Exception as e:
        logger.exception("Error deleting chat session")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting chat session"
        )


@router.delete("/history/{user_id}")
async def clear_user_chat_history(user_id: str):
    """
    Clear all chat history for a user.
    Optimized for memory efficiency.
    
    Args:
        user_id: User identifier
        
    Returns:
        Success message
    """
    try:
        success = clear_all_chat_history(user_id)
        if success:
            log_memory_usage(f"chat history cleared for {user_id}")
            # Clear LLM cache after clearing history to free memory
            clear_llm_cache()
            return {"message": f"All chat history for user {user_id} cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear chat history"
            )
    except Exception as e:
        logger.exception("Error clearing chat history")
        cleanup_memory()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error clearing chat history"
        )

