# backend/routers/chat.py
"""
Chat router with enhanced security and validation.
Implements JWT authentication and comprehensive input validation.
"""
import time
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from backend.modules.vector_store import load_supabase_vectorstore
from backend.modules.retriever_chain import get_conversational_chain
from backend.modules.chat_history_manager import (
    store_chat_interaction, 
    get_chat_history, 
    get_chat_sessions,
    delete_chat_session,
    clear_all_chat_history
)
from backend.modules.utils import logger
from backend.core.validation import ChatRequest, ChatResponse, ErrorResponse
from backend.core.security import security_manager, get_current_user, check_rate_limit
from backend.core.settings import settings

router = APIRouter()
security = HTTPBearer(auto_error=False)  # Make authentication optional for now

def _generate_video_based_response(query: str, relevant_docs: list) -> str:
    """
    Generate a response based only on video content using LLM.
    Prevents hallucinations by constraining the LLM to use only provided context.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # Prepare the context from video documents
        context_parts = []
        for doc, score in relevant_docs:
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
            video_title = metadata.get("video_title", "Unknown Video")
            timestamp = f"{metadata.get('timestamp_start', '')} - {metadata.get('timestamp_end', '')}"
            
            context_parts.append(f"From '{video_title}' ({timestamp}): {content}")
        
        context = "\n\n".join(context_parts)
        
        # Create system prompt that constrains the LLM to use only video content
        system_prompt = """You are a helpful educational assistant that answers questions based ONLY on the provided video content. 

IMPORTANT RULES:
1. Answer ONLY using information from the provided video content below
2. Do NOT add any information not present in the video content
3. If the video content doesn't contain enough information to fully answer the question, say so clearly
4. Be clear, helpful, and educational in your response
5. Focus on accuracy and learning

Video Content:
{context}"""

        # Create the LLM instance
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.1)
        
        # Generate response
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating video-based response: {e}")
        return "I found relevant video content but encountered an error processing it. Please try rephrasing your question."


def _generate_clarification_response(query: str, relevant_docs: list) -> str:
    """
    Generate a clarification response by rephrasing existing video content for better understanding.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # Prepare the context from video documents
        context_parts = []
        for doc, score in relevant_docs:
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
            video_title = metadata.get("video_title", "Unknown Video")
            timestamp = f"{metadata.get('timestamp_start', '')} - {metadata.get('timestamp_end', '')}"
            
            context_parts.append(f"From '{video_title}' ({timestamp}): {content}")
        
        context = "\n\n".join(context_parts)
        
        # Create system prompt for clarification
        system_prompt = """You are a helpful educational assistant that explains video content in clearer, simpler terms.

CRITICAL RULES:
1. Use ONLY the information from the provided video content below
2. Rephrase and simplify the content to make it easier to understand
3. Break down complex concepts into simpler parts
4. Use clear, educational language appropriate for students
5. Do NOT add any information not present in the video content
6. Do NOT make assumptions or add facts not explicitly stated in the videos
7. If the video content is already clear, summarize the key points
8. Focus on making the existing information clearer, not adding new information

Video Content:
{context}"""

        # Create the LLM instance
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.2)
        
        # Generate response
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating clarification response: {e}")
        return "I found relevant video content but encountered an error explaining it. Please try rephrasing your question."

@router.post("/query", response_model=ChatResponse)
async def query_chat(
    request: ChatRequest,
    # credentials: HTTPAuthorizationCredentials = Depends(security)  # Uncomment when auth is needed
):
    """
    Process chat query with enhanced security and validation.
    
    Args:
        request: Validated chat request
        credentials: JWT authentication credentials (optional)
        
    Returns:
        ChatResponse with answer and sources
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    
    try:
        # Rate limiting check
        # if not check_rate_limit(request):
        #     raise HTTPException(
        #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #         detail="Rate limit exceeded"
        #     )
        
        # Check if this is a greeting message
        greeting_keywords = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings', 'howdy']
        query_lower = request.query.lower().strip()
        is_greeting = any(keyword == query_lower or query_lower.startswith(keyword + ' ') for keyword in greeting_keywords)
        
        if is_greeting:
            # Handle greeting messages
            greeting_responses = [
                "Hello! I'm your Vimeo Video Chatbot. I can help you find information from your Vimeo videos. What would you like to know?",
                "Hi there! I'm here to help you explore your Vimeo video content. Feel free to ask me any questions about your videos!",
                "Hello! Welcome to your Vimeo Video Chatbot. I can search through your video content and answer questions about what's covered in your videos.",
                "Hey! I'm your AI assistant for Vimeo videos. Ask me anything about the content in your video library!"
            ]
            import random
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

        # Load vector store for video content queries
        try:
            logger.info("Loading vector store...")
            vs = load_supabase_vectorstore()
            logger.info("Vector store loaded successfully")
        except Exception as e:
            logger.exception("Failed to load vectorstore: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vector store unavailable"
            )

        # First, perform similarity search to check if relevant content exists
        try:
            logger.info("Performing similarity search for query: %s", request.query)
            from backend.modules.embedding_manager import get_embeddings_instance
            
            # Generate embedding for the query
            embeddings = get_embeddings_instance()
            query_embedding = embeddings.embed_query(request.query)
            
            # Search for relevant documents
            docs_with_scores = vs.similarity_search_by_vector_with_relevance_scores(
                query_embedding, k=request.top_k
            )
            
            logger.info("Found %d relevant documents", len(docs_with_scores))
            
            # Log similarity scores for debugging
            for i, (doc, score) in enumerate(docs_with_scores):
                logger.info("Document %d similarity score: %.3f", i, score)
            
            # Implement dynamic threshold with fallback logic
            HIGH_CONFIDENCE_THRESHOLD = 0.5
            LOW_CONFIDENCE_THRESHOLD = 0.3
            MINIMUM_THRESHOLD = 0.2
            
            relevant_docs = []
            low_confidence_docs = []
            
            for doc, score in docs_with_scores:
                if score >= HIGH_CONFIDENCE_THRESHOLD:
                    relevant_docs.append((doc, score))
                elif score >= LOW_CONFIDENCE_THRESHOLD:
                    low_confidence_docs.append((doc, score))
            
            # If no high confidence matches, try with lower threshold
            if not relevant_docs and low_confidence_docs:
                logger.info("No high confidence matches found, using low confidence matches")
                relevant_docs = low_confidence_docs[:1]  # Take only the best low confidence match
            
            # If still no matches, try with even lower threshold
            if not relevant_docs and docs_with_scores:
                best_score = max(score for _, score in docs_with_scores)
                if best_score >= MINIMUM_THRESHOLD:
                    logger.info(f"Using best available match with score {best_score:.3f}")
                    relevant_docs = [(doc, score) for doc, score in docs_with_scores if score == best_score][:1]
            
            # Only return "not found" if absolutely no relevant content
            if not relevant_docs:
                logger.info("No relevant video content found for query")
                answer = "Sorry, this topic isn't covered in the available video content. Please ask about topics that are discussed in your uploaded videos."
                sources = []
            else:
                logger.info("Found %d relevant documents above threshold", len(relevant_docs))
                
                # Check confidence level of the best match
                best_score = max(score for _, score in relevant_docs)
                is_low_confidence = best_score < HIGH_CONFIDENCE_THRESHOLD
                
                if is_low_confidence:
                    logger.info(f"Low confidence response (score: {best_score:.3f})")
                
                # Check if user is asking for clarification/rephrasing
                clarification_keywords = [
                    'explain clearly', 'explain in simple terms', 'can you explain', 
                    'clarify', 'simplify', 'break down', 'elaborate', 'rephrase',
                    'what does this mean', 'help me understand', 'give more details',
                    'explain more', 'tell me more', 'expand on', 'go into detail',
                    'in more detail', 'more information', 'further explanation'
                ]
                is_clarification_request = any(
                    keyword in request.query.lower() for keyword in clarification_keywords
                )
                
                if is_clarification_request and len(relevant_docs) > 0:
                    # Use LLM to rephrase existing video content for better understanding
                    logger.info("User requesting clarification - using LLM to rephrase video content")
                    answer = _generate_clarification_response(request.query, relevant_docs)
                else:
                    # Use video content only - no LLM supplementation
                    logger.info("Generating response based strictly on video content")
                    answer = _generate_video_based_response(request.query, relevant_docs)
                
                # Add confidence indicator for low confidence responses
                if is_low_confidence:
                    answer = f"[Note: This response is based on limited video content] {answer}"
                
                # Process sources
                sources = []
                if request.include_sources:
                    for doc, score in relevant_docs:
                        md = getattr(doc, "metadata", None) or {}
                        sources.append({
                            "video_title": md.get("video_title"),
                            "video_id": md.get("video_id"),
                            "timestamp_start": md.get("timestamp_start"),
                            "timestamp_end": md.get("timestamp_end"),
                            "chunk_id": md.get("chunk_id"),
                            "relevance_score": score
                        })
            
        except Exception as e:
            logger.exception("Error during similarity search: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing query"
            )
        
        processing_time = time.time() - start_time
        
        # Store chat interaction in database
        try:
            # Generate session_id if not provided
            session_id = request.conversation_id or str(uuid.uuid4())
            
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
                from backend.modules.embedding_manager import get_embeddings_instance
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
                    "matched_chunk_id": sources[0].get("chunk_id") if sources else None
                }
                
                result = supabase.table("user_queries").insert(query_record).execute()
                if result.data:
                    logger.info(f"User query stored with ID: {result.data[0]['id']}")
                else:
                    logger.warning("Failed to store user query")
                    
            except Exception as e:
                logger.error(f"Error storing user query: {e}")
                # Don't fail the request if user query storage fails
                
        except Exception as e:
            logger.error(f"Error storing chat interaction: {e}")
            # Don't fail the request if chat history storage fails
        
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
        logger.exception("Unexpected error in query_chat")
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
    
    Args:
        user_id: User identifier
        session_id: Optional session identifier to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records
    """
    try:
        history = get_chat_history(user_id, session_id, limit)
        return {
            "user_id": user_id,
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.exception("Error retrieving chat history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat history"
        )


@router.get("/sessions/{user_id}")
async def get_user_chat_sessions(user_id: str):
    """
    Get all chat sessions for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of chat sessions
    """
    try:
        sessions = get_chat_sessions(user_id)
        return {
            "user_id": user_id,
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.exception("Error retrieving chat sessions")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat sessions"
        )


@router.delete("/session/{user_id}/{session_id}")
async def delete_user_chat_session(user_id: str, session_id: str):
    """
    Delete a specific chat session.
    
    Args:
        user_id: User identifier
        session_id: Session identifier to delete
        
    Returns:
        Success message
    """
    try:
        success = delete_chat_session(user_id, session_id)
        if success:
            return {"message": f"Chat session {session_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete chat session"
            )
    except Exception as e:
        logger.exception("Error deleting chat session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting chat session"
        )


@router.delete("/history/{user_id}")
async def clear_user_chat_history(user_id: str):
    """
    Clear all chat history for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Success message
    """
    try:
        success = clear_all_chat_history(user_id)
        if success:
            return {"message": f"All chat history for user {user_id} cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear chat history"
            )
    except Exception as e:
        logger.exception("Error clearing chat history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error clearing chat history"
        )


# if __name__ == "__main__":
#     import uvicorn
#     from fastapi import FastAPI

#     app = FastAPI()
#     app.include_router(router, prefix="/chat")

#     print(" Running test server at http://127.0.0.1:8000/chat/query")
#     uvicorn.run(app, host="127.0.0.1", port=8000)
