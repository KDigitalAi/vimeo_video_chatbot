"""
User profile management for session handling.
Manages user profiles and active sessions with proper isolation.
"""
from typing import Optional, Dict, Any
from app.database.supabase import get_supabase
from app.core.exceptions import NotFoundError, PersistenceError
from app.utils.logger import logger, log_memory_usage, cleanup_memory
from app.utils.runtime_helpers import memory_guard


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
    memory_guard(logger, "setting active session")
    
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
            logger.info(
                "Active session set",
                component="user_profile",
                operation="set_active_session",
                result="success",
                user_id=user_id,
                session_id=session_id,
                profile_id=profile_id,
            )
            log_memory_usage("session activation")
            return profile_id
        else:
            logger.warning(
                "Active session set returned no data",
                component="user_profile",
                operation="set_active_session",
                result="empty",
                user_id=user_id,
                session_id=session_id,
            )
            return None
            
    except Exception as e:
        logger.exception(
            "Active session set failed",
            component="user_profile",
            operation="set_active_session",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        cleanup_memory()
        raise PersistenceError("Failed to set active session") from e


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
            logger.debug(
                "Active session retrieved",
                component="user_profile",
                operation="get_active_session",
                result="success",
                user_id=user_id,
                session_id=session_id,
            )
            return session_id
        else:
            logger.debug(
                "Active session not found",
                component="user_profile",
                operation="get_active_session",
                result="empty",
                user_id=user_id,
            )
            return None
            
    except Exception as e:
        logger.exception(
            "Active session lookup failed",
            component="user_profile",
            operation="get_active_session",
            result="failure",
            user_id=user_id,
        )
        raise PersistenceError("Failed to get active session") from e


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
        
        result = supabase.table("chatbot_user_profile").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(
                "User profile retrieved",
                component="user_profile",
                operation="get_user_profile",
                result="success",
                user_id=user_id,
            )
            return result.data[0]
        else:
            logger.info(
                "User profile not found",
                component="user_profile",
                operation="get_user_profile",
                result="empty",
                user_id=user_id,
            )
            return None
            
    except Exception as e:
        logger.exception(
            "User profile lookup failed",
            component="user_profile",
            operation="get_user_profile",
            result="failure",
            user_id=user_id,
        )
        raise PersistenceError("Failed to get user profile") from e


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
        
        result = supabase.table("chatbot_user_profile").update({
            "is_active": False
        }).eq("user_id", user_id).eq("session_id", session_id).execute()
        
        if result.data:
            logger.info(
                "Session deactivated",
                component="user_profile",
                operation="deactivate_session",
                result="success",
                user_id=user_id,
                session_id=session_id,
            )
            return True
        else:
            logger.warning(
                "Session not found for deactivation",
                component="user_profile",
                operation="deactivate_session",
                result="empty",
                user_id=user_id,
                session_id=session_id,
            )
            return False
            
    except Exception as e:
        logger.exception(
            "Session deactivation failed",
            component="user_profile",
            operation="deactivate_session",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        raise PersistenceError("Failed to deactivate session") from e


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
        
        result = supabase.table("chatbot_user_profile").update({
            "is_active": False
        }).eq("user_id", user_id).eq("is_active", True).execute()
        
        deactivated_count = len(result.data) if result.data else 0
        logger.info(
            "All sessions deactivated",
            component="user_profile",
            operation="deactivate_all_sessions",
            result="success",
            user_id=user_id,
            deactivated_count=deactivated_count,
        )
        return deactivated_count
        
    except Exception as e:
        logger.exception(
            "All sessions deactivation failed",
            component="user_profile",
            operation="deactivate_all_sessions",
            result="failure",
            user_id=user_id,
        )
        raise PersistenceError("Failed to deactivate all sessions") from e


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
        
        query = supabase.table("chatbot_user_profile").select("*").eq("user_id", user_id)
        
        if not include_inactive:
            query = query.eq("is_active", True)
        
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        
        if result.data:
            logger.debug(
                "User sessions retrieved",
                component="user_profile",
                operation="get_user_sessions",
                result="success",
                user_id=user_id,
                session_count=len(result.data),
                include_inactive=include_inactive,
            )
            return result.data
        else:
            logger.debug(
                "User sessions empty",
                component="user_profile",
                operation="get_user_sessions",
                result="empty",
                user_id=user_id,
                include_inactive=include_inactive,
            )
            return []
            
    except Exception as e:
        logger.exception(
            "User sessions lookup failed",
            component="user_profile",
            operation="get_user_sessions",
            result="failure",
            user_id=user_id,
            include_inactive=include_inactive,
        )
        raise PersistenceError("Failed to get user sessions") from e


# =========================================
# Session-ID Only Functions (user_id ignored)
# =========================================

def set_active_session_by_session_id(session_id: str) -> Optional[str]:
    """
    Set active session using only session_id.
    Since user_id is required in the database function and we do not have a real
    authenticated user_id in this path, use the session_id itself as the fallback identity.
    This keeps session activation isolated per browser/session instead of sharing a global placeholder.
    
    Args:
        session_id: Session identifier to activate
        
    Returns:
        Profile ID (UUID) if successful, None otherwise
    """
    # Check memory before processing
    memory_guard(logger, "setting active session")
    
    try:
        supabase = get_supabase()
        
        # Use session_id as the fallback user_id to prevent cross-user/session collisions.
        # This preserves RPC behavior without changing the database schema or function contract.
        fallback_user_id = session_id
        
        # Use the database function to ensure atomic session management
        result = supabase.rpc(
            "set_active_session",
            {
                "p_user_id": fallback_user_id,
                "p_session_id": session_id
            }
        ).execute()
        
        if result.data:
            profile_id = result.data
            logger.info(
                "Active session set by session id",
                component="user_profile",
                operation="set_active_session_by_id",
                result="success",
                session_id=session_id,
                profile_id=profile_id,
            )
            log_memory_usage("session activation")
            return profile_id
        else:
            logger.warning(
                "Active session set by session id returned no data",
                component="user_profile",
                operation="set_active_session_by_id",
                result="empty",
                session_id=session_id,
            )
            return None
            
    except Exception as e:
        logger.exception(
            "Active session set by session id failed",
            component="user_profile",
            operation="set_active_session_by_id",
            result="failure",
            session_id=session_id,
        )
        cleanup_memory()
        raise PersistenceError("Failed to set active session") from e


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
        result = supabase.table("chatbot_user_profile").update({
            "is_active": False
        }).eq("session_id", session_id).execute()
        
        if result.data:
            logger.info(
                "Session deactivated by session id",
                component="user_profile",
                operation="deactivate_session_by_id",
                result="success",
                session_id=session_id,
            )
            return True
        logger.warning(
            "Session not found for deactivation by session id",
            component="user_profile",
            operation="deactivate_session_by_id",
            result="empty",
            session_id=session_id,
        )
        raise NotFoundError(
            "Session not found",
            details={"session_id": session_id},
        )
            
    except Exception as e:
        logger.exception(
            "Session deactivation by session id failed",
            component="user_profile",
            operation="deactivate_session_by_id",
            result="failure",
            session_id=session_id,
        )
        if isinstance(e, NotFoundError):
            raise
        raise PersistenceError("Failed to deactivate session") from e


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
        
        result = supabase.table("chatbot_user_profile").select("is_active").eq(
            "session_id", session_id
        ).eq("is_active", True).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            logger.debug(
                "Session active state found",
                component="user_profile",
                operation="is_session_active",
                result="success",
                session_id=session_id,
            )
            return result.data[0].get("is_active", False)
        else:
            logger.debug(
                "Session active state empty",
                component="user_profile",
                operation="is_session_active",
                result="empty",
                session_id=session_id,
            )
            return False
            
    except Exception as e:
        logger.exception(
            "Session active state lookup failed",
            component="user_profile",
            operation="is_session_active",
            result="failure",
            session_id=session_id,
        )
        raise PersistenceError("Failed to check session status") from e

