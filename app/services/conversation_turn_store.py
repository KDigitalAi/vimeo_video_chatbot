"""
Chat history management for storing and retrieving chat interactions.
"""
import time
import uuid
from datetime import UTC, datetime
from typing import List, Dict, Optional
from functools import lru_cache
from app.database.supabase import get_supabase
from app.core.exceptions import NotFoundError, PersistenceError
from app.utils.logger import logger, log_memory_usage, cleanup_memory
from app.utils.runtime_helpers import memory_guard

_CACHE_TTL_SECONDS = 30
_session_history_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_user_sessions_cache: dict[str, tuple[float, list[dict]]] = {}


def _get_cached_session_history(session_id: str, limit: int) -> list[dict] | None:
    cached = _session_history_cache.get((session_id, limit))
    if not cached:
        logger.debug(
            "Session history cache miss",
            component="chatbot_chat_history",
            operation="session_history_cache",
            result="miss",
            session_id=session_id,
            limit=limit,
        )
        return None
    expires_at, history = cached
    if expires_at < time.time():
        _session_history_cache.pop((session_id, limit), None)
        logger.debug(
            "Session history cache expired",
            component="chatbot_chat_history",
            operation="session_history_cache",
            result="expired",
            session_id=session_id,
            limit=limit,
        )
        return None
    logger.debug(
        "Session history cache hit",
        component="chatbot_chat_history",
        operation="session_history_cache",
        result="hit",
        session_id=session_id,
        limit=limit,
    )
    return history


def _set_cached_session_history(session_id: str, limit: int, history: list[dict]) -> None:
    _session_history_cache[(session_id, limit)] = (time.time() + _CACHE_TTL_SECONDS, history)


def _get_cached_user_sessions(user_id: str) -> list[dict] | None:
    cached = _user_sessions_cache.get(user_id)
    if not cached:
        logger.debug(
            "User sessions cache miss",
            component="chatbot_chat_history",
            operation="user_sessions_cache",
            result="miss",
            user_id=user_id,
        )
        return None
    expires_at, sessions = cached
    if expires_at < time.time():
        _user_sessions_cache.pop(user_id, None)
        logger.debug(
            "User sessions cache expired",
            component="chatbot_chat_history",
            operation="user_sessions_cache",
            result="expired",
            user_id=user_id,
        )
        return None
    logger.debug(
        "User sessions cache hit",
        component="chatbot_chat_history",
        operation="user_sessions_cache",
        result="hit",
        user_id=user_id,
    )
    return sessions


def _set_cached_user_sessions(user_id: str, sessions: list[dict]) -> None:
    _user_sessions_cache[user_id] = (time.time() + _CACHE_TTL_SECONDS, sessions)


def _invalidate_user_history_cache(user_id: str, session_id: str | None = None) -> None:
    _user_sessions_cache.pop(user_id, None)
    if session_id is None:
        return
    stale_keys = [cache_key for cache_key in _session_history_cache if cache_key[0] == session_id]
    for cache_key in stale_keys:
        _session_history_cache.pop(cache_key, None)


def store_chat_interaction(
    user_id: str,
    session_id: str,
    user_message: str,
    bot_response: str,
) -> Optional[str]:
    """
    Store a chat interaction in the chatbot_chat_history table.
    Optimized for memory efficiency with batch processing.
    
    Args:
        user_id: User identifier
        session_id: Session identifier for grouping related chats
        user_message: The user's message
        bot_response: The bot's response
        
    Returns:
        The ID of the stored chat interaction, or None if failed
    """
    # Check memory before processing
    memory_guard(logger, "storing chat interaction")
    
    try:
        supabase = get_supabase()
        
        # Truncate messages if too long to prevent memory issues
        max_message_length = 10000  # 10KB limit per message
        if len(user_message) > max_message_length:
            user_message = user_message[:max_message_length] + "..."
            logger.warning(
                "User message truncated",
                component="chatbot_chat_history",
                operation="store_chat_interaction",
                result="truncated",
                user_id=user_id,
                session_id=session_id,
                max_message_length=max_message_length,
            )
        
        if len(bot_response) > max_message_length:
            bot_response = bot_response[:max_message_length] + "..."
            logger.warning(
                "Bot response truncated",
                component="chatbot_chat_history",
                operation="store_chat_interaction",
                result="truncated",
                user_id=user_id,
                session_id=session_id,
                max_message_length=max_message_length,
            )
        
        chat_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "created_at": datetime.now(UTC).isoformat()
        }
        
        logger.info(
            "Persisting chat interaction",
            component="chatbot_chat_history",
            operation="store_chat_interaction",
            result="started",
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(
            "Using table: chatbot_chat_history",
            component="chatbot_chat_history",
            operation="store_chat_interaction",
            result="table_selected",
            user_id=user_id,
            session_id=session_id,
        )
        result = supabase.table("chatbot_chat_history").insert(chat_record).execute()
        
        if result.data:
            chat_id = result.data[0]["id"]
            logger.info(
                "Chat interaction persisted",
                component="chatbot_chat_history",
                operation="store_chat_interaction",
                result="success",
                user_id=user_id,
                session_id=session_id,
                chat_id=chat_id,
            )
            _invalidate_user_history_cache(user_id, session_id)
            log_memory_usage("chat storage")
            return chat_id
        logger.error(
            "Chat interaction persistence returned no data",
            component="chatbot_chat_history",
            operation="store_chat_interaction",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        raise PersistenceError("Failed to store chat interaction")
            
    except Exception as e:
        logger.exception(
            "Chat interaction persistence failed",
            component="chatbot_chat_history",
            operation="store_chat_interaction",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        cleanup_memory()
        if isinstance(e, PersistenceError):
            raise
        raise PersistenceError("Failed to store chat interaction") from e


@lru_cache(maxsize=32)
def list_conversation_turns_for_user(
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
    memory_guard(logger, "retrieving chat history")
    
    try:
        supabase = get_supabase()
        
        # Limit the number of records to prevent memory issues
        max_limit = min(limit, 100)  # Cap at 100 records

        logger.info(
            "Using table: chatbot_chat_history",
            component="chatbot_chat_history",
            operation="list_conversation_turns_for_user",
            result="table_selected",
            user_id=user_id,
            session_id=session_id,
        )
        query = supabase.table("chatbot_chat_history").select("*")
        
        # Always filter by user_id
        query = query.eq("user_id", user_id)
        
        # If session_id is provided, also filter by session_id
        if session_id:
            query = query.eq("session_id", session_id)
        
        query = query.order("created_at", desc=True).limit(max_limit)
        
        result = query.execute()
        
        if result.data:
            logger.info(
                "Chat history retrieved",
                component="chatbot_chat_history",
                operation="list_conversation_turns_for_user",
                result="success",
                user_id=user_id,
                session_id=session_id,
                history_count=len(result.data),
            )
            log_memory_usage("chat history retrieval")
            return result.data
        else:
            logger.info(
                "Chat history empty",
                component="chatbot_chat_history",
                operation="list_conversation_turns_for_user",
                result="empty",
                user_id=user_id,
                session_id=session_id,
            )
            return []
            
    except Exception as e:
        logger.exception(
            "Chat history retrieval failed",
            component="chatbot_chat_history",
            operation="list_conversation_turns_for_user",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        cleanup_memory()
        raise PersistenceError("Failed to retrieve chat history") from e


def list_conversation_turns_for_session(session_id: str, limit: int = 50) -> List[Dict]:
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
    memory_guard(logger, "retrieving chat history")
    cached_history = _get_cached_session_history(session_id, limit)
    if cached_history is not None:
        return cached_history
    
    try:
        supabase = get_supabase()
        
        # Limit the number of records to prevent memory issues
        max_limit = min(limit, 100)  # Cap at 100 records
        
        # Filter ONLY by session_id (user_id is ignored)
        query = supabase.table("chatbot_chat_history").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=True).limit(max_limit)
        
        result = query.execute()
        
        if result.data:
            logger.info(
                "Session chat history retrieved",
                component="chatbot_chat_history",
                operation="get_session_history",
                result="success",
                session_id=session_id,
                history_count=len(result.data),
            )
            log_memory_usage("chat history retrieval")
            _set_cached_session_history(session_id, limit, result.data)
            return result.data
        else:
            logger.info(
                "Session chat history empty",
                component="chatbot_chat_history",
                operation="get_session_history",
                result="empty",
                session_id=session_id,
            )
            _set_cached_session_history(session_id, limit, [])
            return []
            
    except Exception as e:
        logger.exception(
            "Session chat history retrieval failed",
            component="chatbot_chat_history",
            operation="get_session_history",
            result="failure",
            session_id=session_id,
        )
        cleanup_memory()
        raise PersistenceError("Failed to retrieve session chat history") from e


def get_chat_sessions(user_id: str) -> List[Dict]:
    """
    Get all chat sessions for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of unique session records with metadata
    """
    cached_sessions = _get_cached_user_sessions(user_id)
    if cached_sessions is not None:
        return cached_sessions
    try:
        supabase = get_supabase()

        logger.info(
            "Using table: chatbot_chat_history",
            component="chatbot_chat_history",
            operation="get_user_sessions",
            result="table_selected",
            user_id=user_id,
        )
        # Fetch recent rows first, then keep the newest row per session.
        result = supabase.table("chatbot_chat_history").select(
            "session_id, created_at, user_message"
        ).eq("user_id", user_id).order("created_at", desc=True).limit(500).execute()
        
        if result.data:
            seen_session_ids = set()
            session_list = []
            for record in result.data:
                session_id = record.get("session_id")
                if not session_id or session_id in seen_session_ids:
                    continue
                seen_session_ids.add(session_id)
                session_list.append(
                    {
                        "session_id": session_id,
                        "last_message": record.get("user_message"),
                        "last_activity": record.get("created_at"),
                    }
                )
            logger.info(
                "User chat sessions retrieved",
                component="chatbot_chat_history",
                operation="get_user_sessions",
                result="success",
                user_id=user_id,
                session_count=len(session_list),
            )
            _set_cached_user_sessions(user_id, session_list)
            return session_list
        else:
            logger.info(
                "User chat sessions empty",
                component="chatbot_chat_history",
                operation="get_user_sessions",
                result="empty",
                user_id=user_id,
            )
            _set_cached_user_sessions(user_id, [])
            return []
            
    except Exception as e:
        logger.exception(
            "User chat sessions retrieval failed",
            component="chatbot_chat_history",
            operation="get_user_sessions",
            result="failure",
            user_id=user_id,
        )
        raise PersistenceError("Failed to retrieve chat sessions") from e


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

        logger.info(
            "Using table: chatbot_chat_history",
            component="chatbot_chat_history",
            operation="delete_chat_session",
            result="table_selected",
            user_id=user_id,
            session_id=session_id,
        )
        result = supabase.table("chatbot_chat_history").delete().eq(
            "user_id", user_id
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise NotFoundError(
                "Chat session not found",
                details={"user_id": user_id, "session_id": session_id},
            )
        _invalidate_user_history_cache(user_id, session_id)
        logger.info(
            "Chat session deleted",
            component="chatbot_chat_history",
            operation="delete_chat_session",
            result="success",
            user_id=user_id,
            session_id=session_id,
        )
        return True
        
    except Exception as e:
        logger.exception(
            "Chat session deletion failed",
            component="chatbot_chat_history",
            operation="delete_chat_session",
            result="failure",
            user_id=user_id,
            session_id=session_id,
        )
        if isinstance(e, NotFoundError):
            raise
        raise PersistenceError("Failed to delete chat session") from e


def clear_all_conversation_turns_for_user(user_id: str) -> bool:
    """
    Clear all chat history for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase()

        logger.info(
            "Using table: chatbot_chat_history",
            component="chatbot_chat_history",
            operation="clear_conversation_turns_for_user",
            result="table_selected",
            user_id=user_id,
        )
        result = supabase.table("chatbot_chat_history").delete().eq("user_id", user_id).execute()

        if not result.data:
            raise NotFoundError(
                "No chat history found for user",
                details={"user_id": user_id},
            )
        _invalidate_user_history_cache(user_id)
        logger.info(
            "User chat history cleared",
            component="chatbot_chat_history",
            operation="clear_conversation_turns_for_user",
            result="success",
            user_id=user_id,
        )
        return True
        
    except Exception as e:
        logger.exception(
            "User chat history clear failed",
            component="chatbot_chat_history",
            operation="clear_conversation_turns_for_user",
            result="failure",
            user_id=user_id,
        )
        if isinstance(e, NotFoundError):
            raise
        raise PersistenceError("Failed to clear chat history") from e
