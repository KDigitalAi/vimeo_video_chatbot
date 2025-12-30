"""
Chat history management for storing and retrieving chat interactions.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from functools import lru_cache
from app.database.supabase import get_supabase
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold


def store_chat_interaction(
    user_id: str,
    session_id: str,
    user_message: str,
    bot_response: str,
    video_id: Optional[str] = None
) -> Optional[str]:
    """
    Store a chat interaction in the chat_history table.
    Optimized for memory efficiency with batch processing.
    
    Args:
        user_id: User identifier
        session_id: Session identifier for grouping related chats
        user_message: The user's message
        bot_response: The bot's response
        video_id: Video ID (deprecated - PDF-only mode, kept for database compatibility)
        
    Returns:
        The ID of the stored chat interaction, or None if failed
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before storing chat interaction")
        cleanup_memory()
    
    try:
        supabase = get_supabase()
        
        # Truncate messages if too long to prevent memory issues
        max_message_length = 10000  # 10KB limit per message
        if len(user_message) > max_message_length:
            user_message = user_message[:max_message_length] + "..."
            logger.warning(f"User message truncated to {max_message_length} characters")
        
        if len(bot_response) > max_message_length:
            bot_response = bot_response[:max_message_length] + "..."
            logger.warning(f"Bot response truncated to {max_message_length} characters")
        
        chat_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("chat_history").insert(chat_record).execute()
        
        if result.data:
            chat_id = result.data[0]["id"]
            logger.info(f"Chat interaction stored successfully with ID: {chat_id}")
            log_memory_usage("chat storage")
            return chat_id
        else:
            logger.error("Failed to store chat interaction - no data returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to store chat interaction: {e}")
        cleanup_memory()
        return None


@lru_cache(maxsize=32)
def get_chat_history(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Retrieve chat history for a user or session.
    Optimized with caching to reduce database calls.
    
    Args:
        user_id: User identifier
        session_id: Optional session identifier to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before retrieving chat history")
        cleanup_memory()
    
    try:
        supabase = get_supabase()
        
        # Limit the number of records to prevent memory issues
        max_limit = min(limit, 100)  # Cap at 100 records
        
        query = supabase.table("chat_history").select("*")
        
        # Always filter by user_id
        query = query.eq("user_id", user_id)
        
        # If session_id is provided, also filter by session_id
        if session_id:
            query = query.eq("session_id", session_id)
        
        query = query.order("created_at", desc=True).limit(max_limit)
        
        result = query.execute()
        
        if result.data:
            logger.info(f"Retrieved {len(result.data)} chat history records")
            log_memory_usage("chat history retrieval")
            return result.data
        else:
            logger.info("No chat history found")
            return []
            
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
        cleanup_memory()
        return []


def get_chat_history_by_session(session_id: str, limit: int = 50) -> List[Dict]:
    """
    Retrieve chat history for a specific session (session_id only, user_id ignored).
    This ensures only data from the specified session is returned.
    
    Args:
        session_id: Session identifier to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records for this session only
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before retrieving chat history")
        cleanup_memory()
    
    try:
        supabase = get_supabase()
        
        # Limit the number of records to prevent memory issues
        max_limit = min(limit, 100)  # Cap at 100 records
        
        # Filter ONLY by session_id (user_id is ignored)
        query = supabase.table("chat_history").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=True).limit(max_limit)
        
        result = query.execute()
        
        if result.data:
            logger.info(f"Retrieved {len(result.data)} chat history records for session {session_id}")
            log_memory_usage("chat history retrieval")
            return result.data
        else:
            logger.info(f"No chat history found for session {session_id}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to retrieve chat history for session {session_id}: {e}")
        cleanup_memory()
        return []


def get_chat_sessions(user_id: str) -> List[Dict]:
    """
    Get all chat sessions for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of unique session records with metadata
    """
    try:
        supabase = get_supabase()
        
        # Get unique sessions with their latest message
        result = supabase.table("chat_history").select(
            "session_id, created_at, user_message"
        ).eq("user_id", user_id).order("created_at", desc=True).execute()
        
        if result.data:
            # Optimized grouping with O(n) complexity using dict comprehension
            sessions = {
                record["session_id"]: {
                    "session_id": record["session_id"],
                    "last_message": record["user_message"],
                    "last_activity": record["created_at"]
                }
                for record in result.data
            }
            
            session_list = list(sessions.values())
            logger.info(f"Retrieved {len(session_list)} chat sessions")
            return session_list
        else:
            logger.info("No chat sessions found")
            return []
            
    except Exception as e:
        logger.error(f"Failed to retrieve chat sessions: {e}")
        return []


def delete_chat_session(user_id: str, session_id: str) -> bool:
    """
    Delete all chat history for a specific session.
    
    Args:
        user_id: User identifier
        session_id: Session identifier to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("chat_history").delete().eq(
            "user_id", user_id
        ).eq("session_id", session_id).execute()
        
        logger.info(f"Deleted chat session {session_id} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete chat session: {e}")
        return False


def clear_all_chat_history(user_id: str) -> bool:
    """
    Clear all chat history for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("chat_history").delete().eq("user_id", user_id).execute()
        
        logger.info(f"Cleared all chat history for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear chat history: {e}")
        return False
