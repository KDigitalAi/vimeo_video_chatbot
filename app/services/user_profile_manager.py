"""
User profile management for session handling.
Manages user profiles and active sessions with proper isolation.
"""
import uuid
from typing import Optional, Dict, Any
from functools import lru_cache
from app.database.supabase import get_supabase
from app.utils.logger import logger, log_memory_usage, cleanup_memory, check_memory_threshold


def set_active_session(user_id: str, session_id: str) -> Optional[str]:
    """
    Set active session for a user using the database function.
    This ensures only ONE active session per user at a time.
    
    Args:
        user_id: User identifier
        session_id: Session identifier to activate
        
    Returns:
        Profile ID (UUID) if successful, None otherwise
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before setting active session")
        cleanup_memory()
    
    try:
        supabase = get_supabase()
        
        # Use the database function to ensure atomic session management
        result = supabase.rpc(
            "set_active_session",
            {
                "p_user_id": user_id,
                "p_session_id": session_id
            }
        ).execute()
        
        if result.data:
            profile_id = result.data
            logger.info(f"Active session set for user {user_id}: session {session_id} (profile_id: {profile_id})")
            log_memory_usage("session activation")
            return profile_id
        else:
            logger.warning(f"Failed to set active session - no data returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to set active session: {e}")
        cleanup_memory()
        return None


def get_active_session(user_id: str) -> Optional[str]:
    """
    Get the current active session for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Active session_id if found, None otherwise
    """
    try:
        supabase = get_supabase()
        
        # Use the database function for consistent session retrieval
        result = supabase.rpc(
            "get_active_session",
            {
                "p_user_id": user_id
            }
        ).execute()
        
        if result.data:
            session_id = result.data
            logger.debug(f"Active session for user {user_id}: {session_id}")
            return session_id
        else:
            logger.debug(f"No active session found for user {user_id}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to get active session: {e}")
        return None


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile information including active session.
    
    Args:
        user_id: User identifier
        
    Returns:
        User profile dictionary or None if not found
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("user_profile").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        return None


def deactivate_session(user_id: str, session_id: str) -> bool:
    """
    Deactivate a specific session for a user.
    
    Args:
        user_id: User identifier
        session_id: Session identifier to deactivate
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("user_profile").update({
            "is_active": False
        }).eq("user_id", user_id).eq("session_id", session_id).execute()
        
        if result.data:
            logger.info(f"Deactivated session {session_id} for user {user_id}")
            return True
        else:
            logger.warning(f"Session {session_id} not found for user {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to deactivate session: {e}")
        return False


def deactivate_all_sessions(user_id: str) -> int:
    """
    Deactivate all sessions for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Number of sessions deactivated
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("user_profile").update({
            "is_active": False
        }).eq("user_id", user_id).eq("is_active", True).execute()
        
        deactivated_count = len(result.data) if result.data else 0
        logger.info(f"Deactivated {deactivated_count} sessions for user {user_id}")
        return deactivated_count
        
    except Exception as e:
        logger.error(f"Failed to deactivate all sessions: {e}")
        return 0


def get_user_sessions(user_id: str, include_inactive: bool = False) -> list:
    """
    Get all sessions for a user.
    
    Args:
        user_id: User identifier
        include_inactive: Whether to include inactive sessions
        
    Returns:
        List of session records
    """
    try:
        supabase = get_supabase()
        
        query = supabase.table("user_profile").select("*").eq("user_id", user_id)
        
        if not include_inactive:
            query = query.eq("is_active", True)
        
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        
        if result.data:
            logger.debug(f"Retrieved {len(result.data)} sessions for user {user_id}")
            return result.data
        else:
            return []
            
    except Exception as e:
        logger.error(f"Failed to get user sessions: {e}")
        return []


# =========================================
# Session-ID Only Functions (user_id ignored)
# =========================================

def set_active_session_by_session_id(session_id: str) -> Optional[str]:
    """
    Set active session using only session_id.
    Since user_id is required in database, we use session_id as user_id.
    
    Args:
        session_id: Session identifier to activate
        
    Returns:
        Profile ID (UUID) if successful, None otherwise
    """
    # Check memory before processing
    if not check_memory_threshold():
        logger.warning("Memory usage high before setting active session")
        cleanup_memory()
    
    try:
        supabase = get_supabase()
        
        # Use session_id as user_id (since we're ignoring user_id)
        # This allows the database structure to remain unchanged
        user_id_placeholder = session_id
        
        # Use the database function to ensure atomic session management
        result = supabase.rpc(
            "set_active_session",
            {
                "p_user_id": user_id_placeholder,
                "p_session_id": session_id
            }
        ).execute()
        
        if result.data:
            profile_id = result.data
            logger.info(f"Active session set: {session_id} (profile_id: {profile_id})")
            log_memory_usage("session activation")
            return profile_id
        else:
            logger.warning(f"Failed to set active session - no data returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to set active session: {e}")
        cleanup_memory()
        return None


def deactivate_session_by_id(session_id: str) -> bool:
    """
    Deactivate a session using only session_id.
    
    Args:
        session_id: Session identifier to deactivate
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase()
        
        # Deactivate by session_id only (user_id is ignored)
        result = supabase.table("user_profile").update({
            "is_active": False
        }).eq("session_id", session_id).execute()
        
        if result.data:
            logger.info(f"Deactivated session {session_id}")
            return True
        else:
            logger.warning(f"Session {session_id} not found")
            return False
            
    except Exception as e:
        logger.error(f"Failed to deactivate session: {e}")
        return False


def is_session_active(session_id: str) -> bool:
    """
    Check if a session is active using only session_id.
    
    Args:
        session_id: Session identifier to check
        
    Returns:
        True if session is active, False otherwise
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("user_profile").select("is_active").eq(
            "session_id", session_id
        ).eq("is_active", True).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0].get("is_active", False)
        else:
            return False
            
    except Exception as e:
        logger.error(f"Failed to check session status: {e}")
        return False

