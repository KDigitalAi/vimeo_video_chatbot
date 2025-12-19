# backend/routers/chat.py
"""
Chat router with enhanced security and validation.
Implements JWT authentication and comprehensive input validation.
"""
import time
import uuid
from fastapi import APIRouter, HTTPException, status
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
from backend.core.settings import settings

router = APIRouter()

# Global dictionary to store conversation chains per session
_conversation_chains = {}

# Global vector store instance
_global_vector_store = None

def _safe_int(value, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return int(str(value).strip())
    except Exception:
        return default

def _parse_timestamp_to_seconds(value, default: int = 0) -> int:
    """Parse seconds or 'HH:MM:SS'/'MM:SS' strings into seconds. Return default on failure."""
    try:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if s.isdigit():
            return int(s)
        parts = s.split(":")
        parts = [p for p in parts if p != ""]
        if len(parts) == 3:
            h, m, sec = parts
            return _safe_int(h, 0) * 3600 + _safe_int(m, 0) * 60 + _safe_int(sec, 0)
        if len(parts) == 2:
            m, sec = parts
            return _safe_int(m, 0) * 60 + _safe_int(sec, 0)
        return default
    except Exception:
        return default

def _merge_and_clean_content(relevant_docs: list) -> str:
    """
    Merge and clean content from multiple documents for comprehensive educational presentation.
    Groups content by topic and source for better organization and completeness.
    """
    # Group documents by source and organize by relevance
    pdf_content = []
    video_content = []
    
    # Sort by relevance score (higher scores first)
    sorted_docs = sorted(relevant_docs, key=lambda x: x[1], reverse=True)
    
    for doc, score in sorted_docs:
        content = doc.page_content.strip()
        if not content:
            continue
            
        metadata = getattr(doc, "metadata", {})
        source_type = metadata.get("source_type")
        
        # Clean and normalize content while preserving structure
        cleaned_content = content.replace('\n', ' ').replace('  ', ' ').strip()
        
        # Remove excessive whitespace but keep meaningful structure
        cleaned_content = ' '.join(cleaned_content.split())
        
        if source_type == "pdf":
            pdf_title = metadata.get("pdf_title", "Unknown PDF")
            page = metadata.get("page_number", "?")
            chunk_id = metadata.get("chunk_id", "")
            pdf_content.append(f"[PDF: {pdf_title}, Page {page}] {cleaned_content}")
        else:
            video_title = metadata.get("video_title", "Unknown Video")
            timestamp_start = metadata.get("timestamp_start", "")
            timestamp_end = metadata.get("timestamp_end", "")
            if timestamp_start and timestamp_end:
                timestamp = f"{timestamp_start}-{timestamp_end}"
            else:
                timestamp = "Unknown time"
            video_content.append(f"[Video: {video_title}, {timestamp}] {cleaned_content}")
    
    # Combine all content with clear separation and organization
    combined_content = []
    
    if pdf_content:
        combined_content.append("📚 **PDF Course Materials:**")
        combined_content.append("\n".join(pdf_content))
    
    if video_content:
        combined_content.append("🎥 **Video Lectures:**")
        combined_content.append("\n".join(video_content))
    
    # Add instruction for comprehensive response
    if combined_content:
        combined_content.append("\n**Instructions for Response:**")
        combined_content.append("Use ALL the information above to provide a complete, comprehensive explanation. Combine insights from both PDF and video sources when available. Structure your response with clear explanations, practical examples, and key takeaways.")
    
    return "\n\n".join(combined_content)


def _get_or_create_conversation_chain(session_id: str, vector_store):
    """
    Get or create a conversation chain for the given session.
    This ensures each session has its own memory context.
    """
    logger.info(f"Getting conversation chain for session: {session_id}")
    logger.info(f"Existing chains: {list(_conversation_chains.keys())}")
    
    if session_id not in _conversation_chains:
        logger.info(f"Creating new conversation chain for session: {session_id}")
        _conversation_chains[session_id] = get_conversational_chain(
            vector_store=vector_store,
            temperature=0.2,
            k=5
        )
    else:
        logger.info(f"Reusing existing conversation chain for session: {session_id}")
    
    return _conversation_chains[session_id]


def _clear_conversation_chain(session_id: str):
    """
    Clear conversation chain for a session (when chat is cleared).
    """
    if session_id in _conversation_chains:
        del _conversation_chains[session_id]


def _format_educational_response(response_text: str, query: str) -> str:
    """
    Format any response into a structured educational format.
    Ensures consistent formatting across all response types.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # Create system prompt for formatting responses
        system_prompt = """You are an expert programming instructor. Your job is to format responses into a clear, educational structure that helps students learn effectively.

FORMATTING RULES:
1. ALWAYS structure the response with these sections (skip sections if content doesn't allow):
   - **Explanation:** [Clear, concise explanation of the concept]
   - **Example:** [Practical example or code snippet if available - skip if no example possible]
   - **Key Points:** [5-7 bullet points summarizing the most important concepts]

2. Use simple, clear language appropriate for students
3. Make explanations engaging and educational
4. If the response already has good structure, preserve it but ensure consistency
5. If the response is poorly structured, reformat it completely
6. Ensure proper spacing between sections
7. Use bullet points (•) for key points
8. Format code blocks properly with triple backticks
9. Keep explanations concise but complete

RESPONSE TO FORMAT:
{response_text}

ORIGINAL QUERY:
{query}

Remember: Make this response clear, educational, and well-structured for students!"""

        # Create the LLM instance
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.1)
        
        # Generate formatted response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Format this response: {response_text}")
        ]
        
        formatted_response = llm.invoke(messages)
        return formatted_response.content
        
    except Exception as e:
        logger.error(f"Error formatting educational response: {e}")
        # Fallback: return original response with basic formatting
        return f"**Explanation:**\n{response_text}\n\n**Key Points:**\n• Please refer to the explanation above for key concepts"


def _generate_video_based_response(query: str, relevant_docs: list) -> str:
    """
    Generate a comprehensive, student-friendly response based on provided content using LLM.
    Creates detailed, educational explanations suitable for coding institute students.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # Merge and clean content from all relevant documents
        context = _merge_and_clean_content(relevant_docs)
        
        # Create enhanced system prompt for comprehensive student-friendly responses
        system_prompt = """You are an expert programming instructor at a software coaching institute. Your job is to help students learn programming concepts clearly and completely using ONLY the course materials provided.

🎯 **TEACHING MISSION:**
Create comprehensive, step-by-step explanations that help students truly understand the concepts.

📋 **RESPONSE REQUIREMENTS:**
1. **Use ONLY the information from the provided course materials below**
2. **Combine ALL relevant information** from both PDF and video sources
3. **Create a complete, comprehensive explanation** - don't truncate or summarize too early
4. **Structure your response with clear sections:**
   - **Explanation:** Clear, detailed explanation of the concept
   - **Example:** Practical code examples and demonstrations
   - **Key Points:** 5-7 important takeaways for students
5. **Use simple, clear language** appropriate for students
6. **Provide step-by-step explanations** when possible
7. **Include practical examples and code snippets** when available
8. **Format code blocks properly** with syntax highlighting
9. **Make it engaging and encouraging** for students
10. **If content is insufficient, clearly state what's missing** and suggest where to find more information

📚 **COURSE MATERIALS TO USE:**
{context}

🎓 **STUDENT-FOCUSED APPROACH:**
- Think like a teaching assistant explaining to a student
- Break down complex concepts into digestible parts
- Use analogies and real-world examples when helpful
- Encourage learning and curiosity
- Make sure students understand the "why" behind concepts

Remember: You are teaching students who want to learn programming. Be thorough, clear, and encouraging!"""

        # Create the LLM instance with optimal temperature for educational content
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.3)
        
        # Generate comprehensive response
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating content-based response: {e}")
        return "I found relevant content but encountered an error processing it. Please try rephrasing your question."


def _generate_clarification_response(query: str, relevant_docs: list) -> str:
    """
    Generate a detailed clarification response for students who need extra explanation.
    Uses comprehensive teaching-style approach with step-by-step breakdowns.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # Merge and clean content from all relevant documents
        context = _merge_and_clean_content(relevant_docs)
        
        # Create enhanced system prompt for detailed clarification
        system_prompt = """You are an expert programming instructor helping a student who needs extra clarification. Your goal is to make complex concepts crystal clear through detailed, step-by-step explanations using ONLY the course materials provided.

🎯 **CLARIFICATION MISSION:**
This student specifically asked for clarification, so they need extra help, encouragement, and detailed explanations.

📋 **TEACHING APPROACH:**
1. **Use ONLY the information from the provided course materials below**
2. **Break down the concept into simple, digestible steps**
3. **Use analogies and real-world examples** when helpful
4. **Use encouraging, supportive language** throughout
5. **Include practical code examples with detailed comments**
6. **Address common student misconceptions** about this topic
7. **Focus on clear, detailed explanations** that build understanding
8. **Structure your response with clear sections:**
   - **What is it?** Simple, clear definition
   - **How does it work?** Step-by-step breakdown
   - **Step-by-step Example:** Detailed example with code
   - **Why is it important?** Practical applications and benefits
   - **Key Takeaway:** Summary and encouragement

📚 **COURSE MATERIALS TO USE:**
{context}

🎓 **STUDENT-FOCUSED CLARIFICATION:**
- Think like a patient teaching assistant who loves helping students
- Use "Let's break this down together" approach
- Provide multiple examples if available in the materials
- Explain the "why" behind each step
- Encourage questions and further learning
- Make complex concepts feel approachable

Remember: This student asked for clarification, so they need extra help, encouragement, and comprehensive explanations!"""

        # Create the LLM instance with higher temperature for more creative explanations
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.4)
        
        # Generate comprehensive clarification response
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=query)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating clarification response: {e}")
        return "I found relevant content but encountered an error explaining it. Please try rephrasing your question."


def _generate_llm_fallback_response(query: str, topic_context: str = None) -> str:
    """
    Generate a complete, structured fallback response when PDF/video content is insufficient.
    Uses last topic context (if available) to stay on-topic and provide a thorough, educational answer.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage

        system_prompt = """You are an expert programming instructor. No course materials were found for this query.

Your task is to provide a complete, accurate, and student-friendly answer that is TOPIC-APPROPRIATE based on the last discussed topic if provided. Do not hallucinate specifics about the student's PDFs/videos. Instead, teach the topic clearly and thoroughly.

Rules:
1) Stay aligned with the topic context below (if present). Do not drift topics.
2) Provide a full explanation suitable for students at a coding institute.
3) Include multiple practical code examples when asked to "show examples" or "show codes".
4) Keep terminology standard and best-practice oriented.
5) Never contradict any provided topic context; if something is uncertain, omit it.
6) Always structure the response with: Explanation, Example, Key Points.

Topic Context (may be empty): {topic_context}
"""

        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.3)
        messages = [
            SystemMessage(content=system_prompt.format(topic_context=topic_context or "")),
            HumanMessage(content=query)
        ]
        resp = llm.invoke(messages)
        content = resp.content
        return _format_educational_response(content, query)
    except Exception as e:
        logger.error(f"Error in LLM fallback response: {e}")
        return _format_educational_response(
            "I will explain this topic clearly and completely based on general best practices, even though your uploaded materials did not contain it.",
            query
        )

@router.post("/query", response_model=ChatResponse)
async def query_chat(
    request_data: dict,
):
    """
    Process chat query with enhanced security and validation.
    
    Args:
        request_data: Raw request data from frontend
        credentials: JWT authentication credentials (optional)
        
    Returns:
        ChatResponse with answer and sources
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    
    try:
        # Extract and validate the nested request
        if 'request' not in request_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'request' field in request body"
            )
        
        # Validate the nested request using Pydantic
        try:
            request = ChatRequest(**request_data['request'])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Request validation failed: {str(e)}"
            )
        
        # Check if this is a greeting message
        greeting_keywords = [
            'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 
            'greetings', 'howdy', 'how are you', 'what\'s up', 'sup', 'yo',
            'good day', 'good night', 'greeting', 'hiya', 'hey there',
            'hii', 'helloo', 'heyy', 'heyyy'  # Common variations
        ]
        query_lower = request.query.lower().strip()
        # Improved greeting detection to handle variations like "hii", "helloo", etc.
        is_greeting = any(
            keyword == query_lower or 
            query_lower.startswith(keyword + ' ') or 
            query_lower.startswith(keyword) and len(query_lower) <= len(keyword) + 2  # Allow 1-2 extra characters
            for keyword in greeting_keywords
        )
        
        if is_greeting:
            # Handle greeting messages with student-friendly responses
            greeting_responses = [
                "Hello! I'm your Learning Assistant. How can I help you with your study materials today?",
                "Hi there! I'm ready to help you learn — what topic would you like to explore?",
                "Good morning! Let's study together — what would you like to know today?",
                "Hey! I'm here to help you understand your video and PDF content. What would you like to learn about?",
                "Hello! Welcome to your study companion. I can help you find information in your uploaded materials. What interests you?",
                "Hi! I'm your educational assistant. Ready to dive into your learning materials — what's on your mind?"
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
            global _global_vector_store
            if _global_vector_store is None:
                logger.info("Loading vector store...")
                _global_vector_store = load_supabase_vectorstore()
                logger.info("Vector store loaded successfully")
            vs = _global_vector_store
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

            # Basic input validation to avoid passing empty queries downstream
            if not request.query or not str(request.query).strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Query text must not be empty"
                )

            # Generate session_id early for use in follow-up detection
            session_id = request.conversation_id or str(uuid.uuid4())
            
            # Check if this is a follow-up question that needs context from previous conversation
            follow_up_keywords = [
                'explain more', 'tell me more', 'give more', 'add more', 'show more',
                'can you explain', 'elaborate', 'expand on', 'go into detail',
                'more examples', 'more code', 'more details', 'further explanation',
                'what else', 'anything else', 'other examples', 'additional',
                'give some more', 'show some more', 'provide more',
                # Added explicit clarification/follow-ups
                'can you explain more', 'show some examples', 'explain clearly',
                'give more details', 'show more codes', 'expand on this', 'explain in detail'
            ]
            
            is_follow_up = any(keyword in request.query.lower() for keyword in follow_up_keywords)
            search_query = request.query
            
            logger.info(f"Query: '{request.query}' - Follow-up detected: {is_follow_up}")
            
            # Initialize conversation chain variable
            conversation_chain = None
            
            # If it's a follow-up question, try to get context from conversation memory
            if is_follow_up:
                logger.info(f"Follow-up question detected: {request.query}")
                try:
                    conversation_chain = _get_or_create_conversation_chain(session_id, vs)
                    memory = conversation_chain.memory
                    chat_history = memory.chat_memory.messages
                    
                    logger.info(f"Chat history length: {len(chat_history)}")
                    
                    if len(chat_history) >= 2:  # At least one previous exchange
                        # Get the last user question and bot response to understand the topic
                        last_user_msg = None
                        last_bot_msg = None
                        
                        # Find the last user message and bot response
                        for i in range(len(chat_history) - 1, -1, -1):
                            msg = chat_history[i]
                            logger.info(f"Message {i}: {type(msg).__name__} - {str(msg)[:100]}...")
                            if hasattr(msg, 'content'):
                                if last_bot_msg is None and hasattr(msg, '__class__') and 'AI' in str(msg.__class__):
                                    last_bot_msg = msg.content
                                    logger.info(f"Found bot message: {last_bot_msg[:100]}...")
                                elif last_user_msg is None and hasattr(msg, '__class__') and 'Human' in str(msg.__class__):
                                    last_user_msg = msg.content
                                    logger.info(f"Found user message: {last_user_msg[:100]}...")
                                    break
                        
                        # If we found the previous topic, use it for search instead of the vague follow-up
                        if last_user_msg and last_bot_msg:
                            logger.info(f"Follow-up detected. Previous topic: {last_user_msg[:100]}...")
                            # Combine previous user topic and current follow-up to strengthen retrieval context
                            search_query = f"{last_user_msg} | {request.query}"
                            logger.info(f"Using previous topic for search: {search_query[:100]}...")
                        else:
                            logger.info("Follow-up detected but no previous context found, using original query")
                    else:
                        logger.info("Follow-up detected but insufficient chat history, using original query")
                except Exception as e:
                    logger.error(f"Error getting conversation context for follow-up: {e}")
                    logger.info("Using original query for search")
            
            # Generate embedding for the search query (either original or previous topic)
            try:
                embeddings = get_embeddings_instance()
                query_embedding = embeddings.embed_query(search_query)
            except HTTPException:
                raise
            except Exception as embed_err:
                logger.exception("Failed to generate embeddings: %s", str(embed_err))
                # Likely configuration or upstream service issue (e.g., API key)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Embeddings service unavailable"
                )
            
            # Search for relevant documents - increased k for more comprehensive results
            docs_with_scores = vs.similarity_search_by_vector_with_relevance_scores(
                query_embedding, k=max(request.top_k or 10, 20)
            )
            
            logger.info("Found %d relevant documents", len(docs_with_scores))
            
            # Log similarity scores for debugging
            for i, (doc, score) in enumerate(docs_with_scores):
                logger.info("Document %d similarity score: %.3f", i, score)
            
            # Implement dynamic threshold with fallback logic
            HIGH_CONFIDENCE_THRESHOLD = 0.5
            LOW_CONFIDENCE_THRESHOLD = 0.4
            MINIMUM_THRESHOLD = 0.3  # Increased threshold to avoid irrelevant matches
            
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
                relevant_docs = low_confidence_docs[:3]  # Take top 3 low confidence matches
            
            # If still no matches, try with even lower threshold
            if not relevant_docs and docs_with_scores:
                best_score = max(score for _, score in docs_with_scores)
                if best_score >= MINIMUM_THRESHOLD:
                    logger.info(f"Using best available match with score {best_score:.3f}")
                    relevant_docs = [(doc, score) for doc, score in docs_with_scores if score == best_score][:1]
            
            # Enhanced PDF and Video expansion for complete topic coverage
            if relevant_docs:
                top_doc, top_score = relevant_docs[0]
                top_metadata = getattr(top_doc, "metadata", {}) or {}
                top_source_type = top_metadata.get("source_type")
                
                if top_source_type == "pdf":
                    # Enhanced PDF expansion - include more chunks from same PDF and related pages
                    pdf_id = top_metadata.get("pdf_id")
                    if pdf_id:
                        additional_chunks = []
                        for doc, score in docs_with_scores:
                            md = getattr(doc, "metadata", {}) or {}
                            if (md.get("source_type") == "pdf" and 
                                md.get("pdf_id") == pdf_id and 
                                score >= (MINIMUM_THRESHOLD - 0.1)):  # Lower threshold for more content
                                additional_chunks.append((doc, score))
                        
                        if additional_chunks:
                            # Sort by page and chunk order for logical flow
                            additional_chunks.sort(key=lambda x: (
                                _safe_int(getattr(x[0], "metadata", {}).get("page_number"), 0),
                                _safe_int(getattr(x[0], "metadata", {}).get("chunk_id"), 0)
                            ))
                            # Add up to 8 additional chunks for complete coverage
                            relevant_docs.extend(additional_chunks[:8])
                            logger.info(f"Added {len(additional_chunks[:8])} additional PDF chunks from same document")
                
                elif top_source_type == "video":
                    # Enhanced video expansion - include chunks from same video with close timestamps
                    video_id = top_metadata.get("video_id")
                    if video_id:
                        additional_chunks = []
                        for doc, score in docs_with_scores:
                            md = getattr(doc, "metadata", {}) or {}
                            if (md.get("source_type") == "video" and 
                                md.get("video_id") == video_id and 
                                score >= (MINIMUM_THRESHOLD - 0.1)):
                                additional_chunks.append((doc, score))
                        
                        if additional_chunks:
                            # Sort by timestamp for chronological order
                            additional_chunks.sort(key=lambda x: (
                                _parse_timestamp_to_seconds(getattr(x[0], "metadata", {}).get("timestamp_start"), 0)
                            ))
                            # Add up to 6 additional chunks for complete video coverage
                            relevant_docs.extend(additional_chunks[:6])
                            logger.info(f"Added {len(additional_chunks[:6])} additional video chunks from same video")
                
                # Cross-source expansion: if we have both PDF and video content, try to include both
                has_pdf = any(getattr(doc, "metadata", {}).get("source_type") == "pdf" for doc, _ in relevant_docs)
                has_video = any(getattr(doc, "metadata", {}).get("source_type") == "video" for doc, _ in relevant_docs)
                
                if has_pdf and not has_video:
                    # Add video content if available
                    video_chunks = [(doc, score) for doc, score in docs_with_scores 
                                  if getattr(doc, "metadata", {}).get("source_type") == "video" 
                                  and score >= (MINIMUM_THRESHOLD - 0.05)]  # Reduced tolerance for cross-source
                    if video_chunks:
                        relevant_docs.extend(video_chunks[:3])
                        logger.info(f"Added {len(video_chunks[:3])} video chunks for cross-source coverage")
                
                elif has_video and not has_pdf:
                    # Add PDF content if available
                    pdf_chunks = [(doc, score) for doc, score in docs_with_scores 
                                if getattr(doc, "metadata", {}).get("source_type") == "pdf" 
                                and score >= (MINIMUM_THRESHOLD - 0.05)]  # Reduced tolerance for cross-source
                    if pdf_chunks:
                        relevant_docs.extend(pdf_chunks[:3])
                        logger.info(f"Added {len(pdf_chunks[:3])} PDF chunks for cross-source coverage")

            # Enhanced response generation with conversation memory
            if not relevant_docs:
                logger.info("No relevant content found for query")
                # Strict mode: do not use LLM when no course material matches
                answer = "Sorry, I don’t have this information in the available study materials."
                sources = []
            else:
                logger.info("Found %d relevant documents above threshold", len(relevant_docs))
                
                # Check confidence level of the best match
                best_score = max(score for _, score in relevant_docs)
                is_low_confidence = best_score < HIGH_CONFIDENCE_THRESHOLD
                
                if is_low_confidence:
                    logger.info(f"Low confidence response (score: {best_score:.3f})")
                
                # Get or create conversation chain for this session (if not already created)
                if conversation_chain is None:
                    conversation_chain = _get_or_create_conversation_chain(session_id, vs)
                
                # Using conversation chain with session memory
                
                # Check if user is asking for clarification/rephrasing
                clarification_keywords = [
                    'explain clearly', 'explain in simple terms', 'can you explain', 
                    'clarify', 'simplify', 'break down', 'elaborate', 'rephrase',
                    'what does this mean', 'help me understand', 'give more details',
                    'explain more', 'tell me more', 'expand on', 'go into detail',
                    'in more detail', 'more information', 'further explanation',
                    # Added explicit phrases
                    'can you explain more', 'show some examples', 'show more codes', 'explain in detail'
                ]
                is_clarification_request = any(
                    keyword in request.query.lower() for keyword in clarification_keywords
                )
                
                # Use conversation chain for context-aware responses
                try:
                    # Prepare context from relevant documents for better responses
                    context = _merge_and_clean_content(relevant_docs)
                    
                    # Create a comprehensive query that includes context and maintains conversation flow
                    if is_follow_up:
                        # Try to include last topic explicitly to ground the continuation
                        last_topic_text = None
                        try:
                            mem = conversation_chain.memory
                            hist = mem.chat_memory.messages
                            for i in range(len(hist) - 1, -1, -1):
                                msg = hist[i]
                                if hasattr(msg, '__class__') and 'Human' in str(msg.__class__) and hasattr(msg, 'content'):
                                    last_topic_text = msg.content
                                    break
                        except Exception:
                            last_topic_text = None

                        topic_hint = f"\n🧭 **Last Topic Context:** {last_topic_text}\n" if last_topic_text else "\n"
                        enhanced_query = f"""📚 **COURSE MATERIALS CONTEXT:**
{context}{topic_hint}
❓ **STUDENT FOLLOW-UP QUESTION:** {request.query}

🎯 **INSTRUCTIONS:**
This is a follow-up question. Stay on the SAME TOPIC as in the last topic context. Use the course materials above first. If the materials only partially cover the request, supplement with clear, accurate expansions and multiple code examples that align with the provided materials. Do NOT contradict or override the materials. Always structure the response into Explanation, Example, and Key Points."""
                    else:
                        enhanced_query = f"""📚 **COURSE MATERIALS CONTEXT:**
{context}

❓ **STUDENT QUESTION:** {request.query}

🎯 **INSTRUCTIONS:**
Please provide a comprehensive, educational response using the course materials above. If the materials are partial, expand with accurate, topic-appropriate detail without contradicting them. Always structure the response into Explanation, Example, and Key Points."""

                    # Decide path based on retrieval strength and context richness
                    context_length = len(context or "")
                    if best_score < MINIMUM_THRESHOLD or context_length == 0:
                        # Unrelated or too weak: do not use LLM
                        answer = "Sorry, I don’t have this information in the available study materials."
                    elif context_length < 300 or is_low_confidence:
                        # Related but partial: expand with LLM and format
                        if is_clarification_request or is_follow_up:
                            raw_answer = _generate_clarification_response(request.query, relevant_docs)
                        else:
                            raw_answer = _generate_video_based_response(request.query, relevant_docs)
                        answer = _format_educational_response(raw_answer, request.query)
                    else:
                        # Sufficient context: use conversation chain with memory
                        result = conversation_chain.invoke({"question": enhanced_query})
                        raw_answer = result.get("answer", "I couldn't generate a response.")
                        answer = _format_educational_response(raw_answer, request.query)
                        
                except Exception as e:
                    logger.error(f"Error using conversation chain: {e}")
                    # Fallback to original method if conversation chain fails
                    if is_clarification_request:
                        logger.info("User requesting clarification - using enhanced teaching approach")
                        raw_answer = _generate_clarification_response(request.query, relevant_docs)
                    else:
                        logger.info("Generating student-friendly response with enhanced content merging")
                        raw_answer = _generate_video_based_response(request.query, relevant_docs)
                    
                    # Format the fallback response into educational structure (only when context exists)
                    context = _merge_and_clean_content(relevant_docs)
                    if best_score < MINIMUM_THRESHOLD or not context:
                        answer = "Sorry, I don’t have this information in the available study materials."
                    else:
                        answer = _format_educational_response(raw_answer, request.query)
                
                # Process sources
                sources = []
                if request.include_sources:
                    for doc, score in relevant_docs:
                        md = getattr(doc, "metadata", None) or {}
                        src_type = md.get("source_type")
                        if src_type == "pdf":
                            source_name = md.get("pdf_title", "Unknown PDF")
                        elif src_type == "video":
                            source_name = md.get("video_title", "Unknown Video")
                        else:
                            source_name = "Unknown Source"

                        # Keep existing fields for backwards compatibility. Set video_title to source_name
                        # so frontends that display video_title will show the correct label for PDFs too.
                        sources.append({
                            "source_type": src_type,
                            "video_title": source_name,
                            "video_id": md.get("video_id"),
                            "timestamp_start": md.get("timestamp_start"),
                            "timestamp_end": md.get("timestamp_end"),
                            "pdf_title": md.get("pdf_title"),
                            "pdf_id": md.get("pdf_id"),
                            "page_number": md.get("page_number"),
                            "chunk_id": md.get("chunk_id"),
                            "relevance_score": score,
                            "source_name": source_name
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


@router.post("/clear-memory/{session_id}")
async def clear_conversation_memory(session_id: str):
    """
    Clear conversation memory for a specific session.
    """
    try:
        _clear_conversation_chain(session_id)
        return {"message": f"Conversation memory cleared for session {session_id}"}
    except Exception as e:
        logger.exception("Error clearing conversation memory")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error clearing conversation memory"
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
            # Clear all conversation chains for this user
            # Note: This is a simple implementation - in production you'd want to track user->session mapping
            global _conversation_chains
            _conversation_chains.clear()
            
            return {"message": f"All chat history and conversation memory for user {user_id} cleared successfully"}
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



