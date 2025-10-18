# backend/modules/chat_history_manager.py
"""
Chat history management for storing and retrieving chat interactions.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from backend.core.supabase_client import get_supabase
from backend.modules.utils import logger


def store_chat_interaction(
    user_id: str,
    session_id: str,
    user_message: str,
    bot_response: str,
    video_id: Optional[str] = None
) -> Optional[str]:
    """
    Store a chat interaction in the chat_history table.
    
    Args:
        user_id: User identifier
        session_id: Session identifier for grouping related chats
        user_message: The user's message
        bot_response: The bot's response
        video_id: Video ID if a video was referenced in the response
        
    Returns:
        The ID of the stored chat interaction, or None if failed
    """
    try:
        supabase = get_supabase()
        
        chat_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "video_id": video_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("chat_history").insert(chat_record).execute()
        
        if result.data:
            chat_id = result.data[0]["id"]
            logger.info(f"Chat interaction stored successfully with ID: {chat_id}")
            return chat_id
        else:
            logger.error("Failed to store chat interaction - no data returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to store chat interaction: {e}")
        return None


def get_chat_history(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Retrieve chat history for a user or session.
    
    Args:
        user_id: User identifier
        session_id: Optional session identifier to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records
    """
    try:
        supabase = get_supabase()
        
        query = supabase.table("chat_history").select("*")
        
        if session_id:
            query = query.eq("session_id", session_id)
        else:
            query = query.eq("user_id", user_id)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        
        if result.data:
            logger.info(f"Retrieved {len(result.data)} chat history records")
            return result.data
        else:
            logger.info("No chat history found")
            return []
            
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
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
            # Group by session_id and get the latest message for each
            sessions = {}
            for record in result.data:
                session_id = record["session_id"]
                if session_id not in sessions:
                    sessions[session_id] = {
                        "session_id": session_id,
                        "last_message": record["user_message"],
                        "last_activity": record["created_at"]
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
