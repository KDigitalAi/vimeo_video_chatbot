"""
Chat router with enhanced security and validation.
"""
import asyncio
import os
import time
import uuid
import app.services.chat_tracking as _chat_tracking_module
from fastapi import APIRouter, HTTPException, status, Body
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe
from app.services.chat_session_memory import (
    _conversation_chains,
    MAX_IN_MEMORY_SESSIONS,
    MAX_SESSION_MESSAGES,
    SESSION_TTL_SECONDS,
    _get_or_create_conversation_chain as _session_get_or_create_conversation_chain,
    _clear_conversation_chain as _session_clear_conversation_chain,
)
from app.services.chat_tracking import (
    _dispatch_chat_tracking as _tracking_dispatch_chat_tracking,
)
from app.services.chat_generation import (
    _follow_up_topic_hint as _generation_follow_up_topic_hint,
    _looks_already_structured as _generation_looks_already_structured,
    _format_educational_response as _generation_format_educational_response,
    build_grounded_prompt as _generation_build_grounded_prompt,
    _generate_clarification_response as _generation_generate_clarification_response,
    _generate_weak_hybrid_response as _generation_generate_weak_hybrid_response,
    _generate_context_grounded_response as _generation_generate_context_grounded_response,
)

# Safe imports with error handling for serverless environments
# Try importing with detailed error capture
load_supabase_vectorstore = None
_import_errors = {}
_bootstrap_logger = get_logger_safe(__name__)

try:
    from app.services.vector_store import load_supabase_vectorstore
    if load_supabase_vectorstore is None:
        _import_errors['vector_store'] = "load_supabase_vectorstore function is None"
except ImportError as e:
    import traceback
    error_msg = f"ImportError: {str(e)}"
    _import_errors['vector_store'] = error_msg
    _bootstrap_logger.error(f"Failed to import load_supabase_vectorstore: {error_msg}")
    _bootstrap_logger.error(f"Traceback: {traceback.format_exc()}")
except Exception as e:
    import traceback
    error_msg = f"Unexpected error importing vector_store: {str(e)}"
    _import_errors['vector_store'] = error_msg
    _bootstrap_logger.error(f"Failed to import load_supabase_vectorstore: {error_msg}")
    _bootstrap_logger.error(f"Traceback: {traceback.format_exc()}")

try:
    from app.services.chat_history_manager import (
        store_chat_interaction, 
        get_chat_history, 
        get_chat_history_by_session,
        get_chat_sessions,
        delete_chat_session,
        clear_all_chat_history
    )
except ImportError as e:
    _bootstrap_logger.error(f"Failed to import chat_history_manager functions: {e}")
    store_chat_interaction = None
    get_chat_history = None
    get_chat_history_by_session = None
    get_chat_sessions = None
    delete_chat_session = None
    clear_all_chat_history = None

# Import user profile manager for session management
try:
    from app.services.user_profile_manager import (
        set_active_session_by_session_id,
        deactivate_session_by_id,
        is_session_active
    )
except ImportError as e:
    _bootstrap_logger.error(f"Failed to import user_profile_manager functions: {e}")
    set_active_session_by_session_id = None
    deactivate_session_by_id = None
    is_session_active = None

logger = get_logger_safe(__name__)

ChatRequest = None
ChatResponse = None

# Try importing schemas with step-by-step verification
try:
    import sys
    import os
    
    # First, verify app package can be imported
    try:
        import app
        if not hasattr(app, '__path__'):
            raise ImportError("app is not a package")
    except ImportError as e:
        raise ImportError(f"Cannot import app package: {e}")
    
    # Second, verify app.models can be imported
    try:
        import app.models
        if not hasattr(app.models, '__path__'):
            raise ImportError("app.models is not a package")
    except ImportError as e:
        raise ImportError(f"Cannot import app.models package: {e}")
    
    # Third, try importing the schemas module
    try:
        from app.models import schemas
    except ImportError as e:
        raise ImportError(f"Cannot import app.models.schemas module: {e}")
    
    # Finally, import the classes
    if not hasattr(schemas, 'ChatRequest') or not hasattr(schemas, 'ChatResponse'):
        raise ImportError("ChatRequest or ChatResponse not found in schemas module")
    
    ChatRequest = schemas.ChatRequest
    ChatResponse = schemas.ChatResponse
    
    if ChatRequest is None or ChatResponse is None:
        _import_errors['schemas'] = "ChatRequest or ChatResponse is None after import"
        
except ImportError as e:
    import traceback
    error_msg = f"ImportError: {str(e)}"
    _import_errors['schemas'] = error_msg
    _bootstrap_logger.error(f"Failed to import schemas: {error_msg}")
    _bootstrap_logger.error(f"Traceback: {traceback.format_exc()}")
    # Add diagnostic info
    try:
        import sys
        _bootstrap_logger.error(f"Python path: {sys.path[:5]}")
        _bootstrap_logger.error(f"Current dir: {os.getcwd()}")
        _bootstrap_logger.error(f"File location: {__file__}")
        # Check if app directory exists
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir)))
        app_dir = os.path.join(project_root, "app")
        models_dir = os.path.join(app_dir, "models")
        _bootstrap_logger.error(f"Project root: {project_root}")
        _bootstrap_logger.error(f"App dir exists: {os.path.exists(app_dir)}")
        _bootstrap_logger.error(f"Models dir exists: {os.path.exists(models_dir)}")
        if os.path.exists(models_dir):
            _bootstrap_logger.error(f"Models dir contents: {os.listdir(models_dir)}")
    except Exception as diag_error:
        _bootstrap_logger.error(f"Could not gather diagnostics: {diag_error}")
except Exception as e:
    import traceback
    error_msg = f"Unexpected error importing schemas: {str(e)}"
    _import_errors['schemas'] = error_msg
    _bootstrap_logger.error(f"Failed to import schemas: {error_msg}")
    _bootstrap_logger.error(f"Traceback: {traceback.format_exc()}")

settings = get_settings_safe()

router = APIRouter()

# Global vector store instance
_global_vector_store = None

# RAG / similarity (same scale as Python cosine and 1 - pgvector cosine distance; higher = more similar)
# best_score >= 0.45 => strong PDF-only answering
RAG_HIGH_CONFIDENCE_SCORE = 0.45
# best_score < 0.25 => strict refusal (no LLM)
RAG_MIN_RELEVANCE_THRESHOLD = 0.25
# Merged/usable context must be at least this long or we treat as no usable evidence.
RAG_MIN_CONTEXT_CHARS = 80
PDF_ONLY_REFUSAL_MESSAGE = (
    "Sorry, I can only answer based on the available PDF study materials."
)


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
    
    IMPORTANT: This function may return an empty string even when relevant_docs is not empty.
    This can happen if:
    - All content is filtered out due to being empty/whitespace
    - Content cleaning removes all text
    - All documents have non-PDF source_type (shouldn't happen in PDF-only mode)
    
    Callers MUST check relevant_docs existence, NOT this return value, to determine
    if documents were retrieved. Empty context ≠ no knowledge in PDF-based RAG systems.
    """
    # Group documents by source and organize by relevance (PDF-only mode)
    pdf_content = []
    
    # Sort by relevance score (higher scores first)
    sorted_docs = sorted(relevant_docs, key=lambda x: x[1], reverse=True)
    
    for doc, score in sorted_docs:
        content = doc.page_content.strip()
        if not content:
            continue
            
        metadata = getattr(doc, "metadata", {})
        source_type = metadata.get("source_type", "pdf")
        
        # Only process PDF content (PDF-only mode)
        if source_type != "pdf":
            continue
        
        # Clean and normalize content while preserving structure
        cleaned_content = content.replace('\n', ' ').replace('  ', ' ').strip()
        
        # Remove excessive whitespace but keep meaningful structure
        cleaned_content = ' '.join(cleaned_content.split())
        
        pdf_title = metadata.get("pdf_title", "Unknown PDF")
        page = metadata.get("page_number", "?")
        chunk_id = metadata.get("chunk_id", "")
        pdf_content.append(f"[PDF: {pdf_title}, Page {page}] {cleaned_content}")
    
    # Combine all content with clear separation and organization
    combined_content = []
    
    if pdf_content:
        combined_content.append("📚 **PDF Course Materials:**")
        combined_content.append("\n".join(pdf_content))
    
    # Add instruction for comprehensive response
    if combined_content:
        combined_content.append("\n**Instructions for Response:**")
        combined_content.append("Use ALL the information above to provide a complete, comprehensive explanation. Structure your response with clear explanations, practical examples, and key takeaways.")
    
    return "\n\n".join(combined_content)


def _context_from_relevant_docs(relevant_docs: list) -> str:
    """Build LLM context from chunks; prefers merged/cleaned text, falls back to raw page_content."""
    merged = _merge_and_clean_content(relevant_docs)
    if (merged or "").strip():
        return merged
    parts = []
    for doc, _score in sorted(relevant_docs, key=lambda x: x[1], reverse=True):
        raw = (getattr(doc, "page_content", None) or "").strip()
        if raw:
            parts.append(raw)
    return "\n\n".join(parts)[:12000]


def _get_or_create_conversation_chain(session_id: str, vector_store):
    """Compatibility wrapper around extracted session memory helper."""
    return _session_get_or_create_conversation_chain(session_id, vector_store)


def _clear_conversation_chain(session_id: str):
    """Compatibility wrapper around extracted session memory helper."""
    return _session_clear_conversation_chain(session_id)

async def _dispatch_chat_tracking(
    *,
    user_id: str,
    session_id: str,
    query_text: str,
    answer: str,
    query_embedding,
    sources: list,
):
    """Compatibility wrapper around extracted tracking dispatcher."""
    # Preserve test compatibility: many tests patch app.api.routes.chat.store_chat_interaction.
    # Forward that patched symbol into the extracted tracking module before dispatch.
    _chat_tracking_module.store_chat_interaction = store_chat_interaction
    await _tracking_dispatch_chat_tracking(
        user_id=user_id,
        session_id=session_id,
        query_text=query_text,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
    )


def _load_vector_store():
    """Load and cache the shared vector store instance."""
    try:
        global _global_vector_store
        if _global_vector_store is None:
            if load_supabase_vectorstore is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Vector store service is not available - import failed"
                )
            if settings.is_development:
                logger.info("Loading vector store...")
            _global_vector_store = load_supabase_vectorstore()
            if settings.is_development:
                logger.info("Vector store loaded successfully")
        return _global_vector_store
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load vectorstore: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store unavailable"
        )


def handle_query_embedding(request, vs):
    """Validate the query, detect follow-ups, and compute the query embedding."""
    if settings.is_development:
        logger.info("Performing similarity search for query: %s", request.query)
    from app.services.embedding_manager import get_embeddings_instance

    if not request.query or not str(request.query).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query text must not be empty"
        )

    session_id = request.conversation_id or str(uuid.uuid4())
    follow_up_keywords = [
        'explain more', 'tell me more', 'give more', 'add more', 'show more',
        'can you explain', 'elaborate', 'expand on', 'go into detail',
        'more examples', 'more code', 'more details', 'further explanation',
        'what else', 'anything else', 'other examples', 'additional',
        'give some more', 'show some more', 'provide more',
        'can you explain more', 'show some examples', 'explain clearly',
        'give more details', 'show more codes', 'expand on this', 'explain in detail'
    ]

    is_follow_up = any(keyword in request.query.lower() for keyword in follow_up_keywords)
    search_query = request.query

    if settings.is_development:
        logger.info(f"Query: '{request.query}' - Follow-up detected: {is_follow_up}")

    conversation_chain = None
    if is_follow_up:
        if settings.is_development:
            logger.info(f"Follow-up question detected: {request.query}")
        try:
            conversation_chain = _get_or_create_conversation_chain(session_id, vs)
            memory = conversation_chain.memory
            chat_history = memory.chat_memory.messages

            if len(chat_history) >= 2:
                last_user_msg = None
                last_bot_msg = None

                for i in range(len(chat_history) - 1, -1, -1):
                    msg = chat_history[i]
                    if hasattr(msg, 'content'):
                        if last_bot_msg is None and hasattr(msg, '__class__') and 'AI' in str(msg.__class__):
                            last_bot_msg = msg.content
                        elif last_user_msg is None and hasattr(msg, '__class__') and 'Human' in str(msg.__class__):
                            last_user_msg = msg.content
                            break

                if last_user_msg and last_bot_msg:
                    search_query = f"{last_user_msg} | {request.query}"
        except Exception as e:
            logger.error(f"Error getting conversation context for follow-up: {e}")

    try:
        api_key = settings.OPENAI_API_KEY
        if not api_key or not api_key.strip():
            raise ValueError("OPENAI_API_KEY is empty or not set in .env file")

        if not api_key.startswith("sk-"):
            raise ValueError(f"OPENAI_API_KEY format is invalid (should start with 'sk-', got: {api_key[:10]}...)")

        if not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = api_key
        if settings.is_development:
            logger.info("OPENAI_API_KEY set in environment from settings")

        if settings.is_development:
            logger.info(f"Generating embedding for query: '{search_query[:50]}...'")

        embeddings = get_embeddings_instance()
        query_embedding = embeddings.embed_query(search_query)

        if not query_embedding or len(query_embedding) == 0:
            raise ValueError("Embedding generation returned empty result")

        return {
            "session_id": session_id,
            "is_follow_up": is_follow_up,
            "conversation_chain": conversation_chain,
            "query_embedding": query_embedding,
        }
    except HTTPException:
        raise
    except ValueError as ve:
        error_msg = str(ve)
        logger.error(f"Embedding validation error: {error_msg}")

        if "OPENAI_API_KEY" in error_msg or "API key" in error_msg or "empty" in error_msg.lower():
            detail_msg = f"OpenAI API key configuration error: {error_msg}. Please check your OPENAI_API_KEY in .env file."
        else:
            detail_msg = f"Embedding validation failed: {error_msg}"

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail_msg
        )
    except Exception as embed_err:
        import traceback
        error_str = str(embed_err)
        error_traceback = traceback.format_exc()

        logger.exception(f"Failed to generate embeddings: {type(embed_err).__name__}: {error_str}")
        if settings.is_development:
            logger.error(f"Full traceback:\n{error_traceback}")

        api_key_issue = False
        network_issue = False
        rate_limit_issue = False

        if "401" in error_str or "invalid" in error_str.lower() or "api key" in error_str.lower() or "authentication" in error_str.lower():
            api_key_issue = True
            logger.error("CRITICAL: OpenAI API key appears to be invalid or expired")
        elif "connection" in error_str.lower() or "timeout" in error_str.lower() or "network" in error_str.lower() or "connect" in error_str.lower():
            network_issue = True
            logger.error("CRITICAL: Network issue connecting to OpenAI API")
        elif "rate limit" in error_str.lower() or "429" in error_str or "quota" in error_str.lower():
            rate_limit_issue = True
            logger.error("CRITICAL: OpenAI API rate limit or quota exceeded")

        if api_key_issue:
            detail_msg = "OpenAI API key is invalid or expired. Please check your OPENAI_API_KEY in .env file and ensure it's valid."
        elif network_issue:
            detail_msg = "Unable to connect to OpenAI API. Please check your network connection and try again."
        elif rate_limit_issue:
            detail_msg = "OpenAI API rate limit exceeded. Please wait a few minutes and try again."
        else:
            if settings.is_development:
                detail_msg = f"Embeddings service error: {error_str[:200]}"
            else:
                detail_msg = "Embeddings service temporarily unavailable. Please try again later."

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail_msg
        )


def handle_retrieval(request, vs, query_embedding):
    """Run retrieval and calculate threshold values for downstream gating."""
    docs_with_scores = vs.similarity_search_by_vector_with_relevance_scores(
        query_embedding, k=max(request.top_k or 10, 10)
    )

    if settings.is_development:
        logger.info("Found %d relevant documents", len(docs_with_scores))

    retrieval_best = (
        max(score for _, score in docs_with_scores) if docs_with_scores else None
    )
    retrieval_used_degraded_fallback = any(
        bool((getattr(doc, "metadata", None) or {}).get("retrieval_degraded"))
        for doc, _score in docs_with_scores
    )
    effective_min_relevance_threshold = (
        max(RAG_MIN_RELEVANCE_THRESHOLD, 0.35)
        if retrieval_used_degraded_fallback
        else RAG_MIN_RELEVANCE_THRESHOLD
    )
    effective_high_confidence_score = (
        max(RAG_HIGH_CONFIDENCE_SCORE, 0.50)
        if retrieval_used_degraded_fallback
        else RAG_HIGH_CONFIDENCE_SCORE
    )

    if settings.is_development and docs_with_scores:
        scores = [score for _, score in docs_with_scores]
        logger.info(
            f"Retrieved {len(docs_with_scores)} documents. "
            f"Score range: min={min(scores):.3f}, max={max(scores):.3f}, "
            f"avg={sum(scores)/len(scores):.3f}"
        )

    return {
        "docs_with_scores": docs_with_scores,
        "retrieval_best": retrieval_best,
        "retrieval_used_degraded_fallback": retrieval_used_degraded_fallback,
        "effective_min_relevance_threshold": effective_min_relevance_threshold,
        "effective_high_confidence_score": effective_high_confidence_score,
    }


def apply_gating_logic(docs_with_scores, retrieval_best, effective_min_relevance_threshold, effective_high_confidence_score):
    """Filter retrieved docs into strong/medium evidence and apply refusal gating."""
    relevant_docs = []
    medium_confidence_docs = []

    for doc, score in docs_with_scores:
        if score >= effective_high_confidence_score:
            relevant_docs.append((doc, score))
        elif score >= effective_min_relevance_threshold:
            medium_confidence_docs.append((doc, score))

    if not relevant_docs and medium_confidence_docs:
        relevant_docs = medium_confidence_docs[:3]
        if settings.is_development:
            logger.info(
                "Using %d medium-confidence documents (scores in [%.2f, %.2f))",
                len(relevant_docs),
                effective_min_relevance_threshold,
                effective_high_confidence_score,
            )
    elif not relevant_docs and docs_with_scores and retrieval_best is not None:
        if retrieval_best >= effective_min_relevance_threshold:
            sorted_all = sorted(docs_with_scores, key=lambda x: x[1], reverse=True)
            relevant_docs = sorted_all[:3]
            if settings.is_development:
                logger.info(
                    "Balanced fallback: using top %d docs (best score %.3f)",
                    len(relevant_docs),
                    retrieval_best,
                )

    if relevant_docs:
        top_doc, top_score = relevant_docs[0]
        top_metadata = getattr(top_doc, "metadata", {}) or {}
        top_source_type = top_metadata.get("source_type")

        if top_source_type == "pdf":
            pdf_id = top_metadata.get("pdf_id")
            if pdf_id:
                additional_chunks = []
                seen_chunk_keys = set()
                for existing_doc, _existing_score in relevant_docs:
                    existing_md = getattr(existing_doc, "metadata", {}) or {}
                    seen_chunk_keys.add((
                        existing_md.get("pdf_id"),
                        existing_md.get("chunk_id"),
                        existing_md.get("page_number"),
                    ))
                for doc, score in docs_with_scores:
                    md = getattr(doc, "metadata", {}) or {}
                    chunk_key = (
                        md.get("pdf_id"),
                        md.get("chunk_id"),
                        md.get("page_number"),
                    )
                    if (md.get("source_type") == "pdf" and
                        md.get("pdf_id") == pdf_id and
                        score >= effective_min_relevance_threshold and
                        chunk_key not in seen_chunk_keys):
                        additional_chunks.append((doc, score))
                        seen_chunk_keys.add(chunk_key)

                if additional_chunks:
                    additional_chunks.sort(key=lambda x: (
                        _safe_int(getattr(x[0], "metadata", {}).get("page_number"), 0),
                        _safe_int(getattr(x[0], "metadata", {}).get("chunk_id"), 0)
                    ))
                    relevant_docs.extend(additional_chunks[:8])

    if settings.is_development:
        logger.info(
            f"After threshold filtering: {len(relevant_docs)} relevant docs, "
            f"{len(docs_with_scores)} total retrieved"
        )
        if relevant_docs:
            best_score_after_filter = max(score for _, score in relevant_docs)
            logger.info(f"Best score after filtering: {best_score_after_filter:.3f}")
        elif docs_with_scores:
            best_score_all = max(score for _, score in docs_with_scores)
            logger.warning(
                "All documents filtered out by min relevance. Best score was %.3f "
                "(min=%.2f)",
                best_score_all,
                effective_min_relevance_threshold,
            )

    if not docs_with_scores:
        logger.warning(
            "RAG refusal: docs_with_scores empty (vector RPC/fallback returned nothing). "
            "Check Supabase pdf_embeddings, match_pdf_embeddings, embedding dimensions."
        )
        return {
            "answer": PDF_ONLY_REFUSAL_MESSAGE,
            "sources": [],
            "relevant_docs": relevant_docs,
            "should_refuse": True,
        }
    if retrieval_best is None or retrieval_best < effective_min_relevance_threshold:
        logger.warning(
            "RAG refusal: insufficient similarity (out-of-scope). chunks=%d best=%.4f min=%.2f",
            len(docs_with_scores),
            retrieval_best if retrieval_best is not None else 0.0,
            effective_min_relevance_threshold,
        )
        return {
            "answer": PDF_ONLY_REFUSAL_MESSAGE,
            "sources": [],
            "relevant_docs": relevant_docs,
            "should_refuse": True,
        }
    if not relevant_docs:
        logger.warning(
            "RAG refusal: relevant_docs empty despite %d retrieved chunks (best=%s)",
            len(docs_with_scores),
            f"{retrieval_best:.4f}" if retrieval_best is not None else "n/a",
        )
        return {
            "answer": PDF_ONLY_REFUSAL_MESSAGE,
            "sources": [],
            "relevant_docs": relevant_docs,
            "should_refuse": True,
        }

    return {
        "relevant_docs": relevant_docs,
        "should_refuse": False,
        "is_hybrid_context": retrieval_best < effective_high_confidence_score,
    }


def generate_answer(request, relevant_docs, retrieval_best, effective_high_confidence_score, conversation_chain, session_id, vs, is_follow_up):
    """Generate the grounded answer from curated context."""
    best_score = max(score for _, score in relevant_docs)
    is_hybrid_context = retrieval_best < effective_high_confidence_score

    if conversation_chain is None:
        conversation_chain = _get_or_create_conversation_chain(session_id, vs)

    try:
        context = _context_from_relevant_docs(relevant_docs)
        topic_hint = _follow_up_topic_hint(conversation_chain) if is_follow_up else "\n"

        if not relevant_docs:
            answer = PDF_ONLY_REFUSAL_MESSAGE
        elif len((context or "").strip()) < RAG_MIN_CONTEXT_CHARS:
            logger.warning(
                "RAG refusal: usable context too short (%d chars, min=%d)",
                len((context or "").strip()),
                RAG_MIN_CONTEXT_CHARS,
            )
            answer = PDF_ONLY_REFUSAL_MESSAGE
        elif is_hybrid_context:
            raw_answer = _generate_context_grounded_response(
                request.query,
                context,
                is_hybrid_context=True,
                is_follow_up=is_follow_up,
                topic_hint=topic_hint,
            )
            _refusal_exact = (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip()
            if _refusal_exact:
                answer = PDF_ONLY_REFUSAL_MESSAGE
            else:
                answer = _format_educational_response(
                    raw_answer,
                    request.query,
                    has_relevant_docs=True,
                    hybrid_weak_context=True,
                )
        elif is_follow_up:
            raw_answer = _generate_context_grounded_response(
                request.query,
                context,
                is_hybrid_context=False,
                is_follow_up=True,
                topic_hint=topic_hint,
            )
            if (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip():
                answer = PDF_ONLY_REFUSAL_MESSAGE
            else:
                answer = _format_educational_response(raw_answer, request.query, has_relevant_docs=True)
        else:
            raw_answer = _generate_context_grounded_response(
                request.query,
                context,
                is_hybrid_context=False,
                is_follow_up=False,
                topic_hint=topic_hint,
            )
            if (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip():
                answer = PDF_ONLY_REFUSAL_MESSAGE
            else:
                answer = _format_educational_response(raw_answer, request.query, has_relevant_docs=True)

        try:
            if conversation_chain is not None and hasattr(conversation_chain, "memory"):
                memory = conversation_chain.memory
                if hasattr(memory, "chat_memory"):
                    memory.chat_memory.add_user_message(request.query)
                    memory.chat_memory.add_ai_message(answer)
        except Exception as memory_error:
            logger.warning("Failed to update conversation memory: %s", memory_error)

        return {
            "answer": answer,
            "conversation_chain": conversation_chain,
            "best_score": best_score,
            "is_hybrid_context": is_hybrid_context,
        }
    except Exception as e:
        logger.error(f"Error generating direct context-grounded response: {e}")
        try:
            if is_hybrid_context and relevant_docs:
                raw_answer = _generate_weak_hybrid_response(request.query, relevant_docs)
                if (raw_answer or "").strip() == PDF_ONLY_REFUSAL_MESSAGE.strip():
                    answer = PDF_ONLY_REFUSAL_MESSAGE
                else:
                    answer = _format_educational_response(
                        raw_answer,
                        request.query,
                        has_relevant_docs=True,
                        hybrid_weak_context=True,
                    )
            elif relevant_docs:
                raw_answer = _generate_clarification_response(request.query, relevant_docs)
                answer = _format_educational_response(
                    raw_answer, request.query, has_relevant_docs=True
                )
            else:
                answer = PDF_ONLY_REFUSAL_MESSAGE
        except Exception as fallback_error:
            logger.error(f"Error in fallback response: {fallback_error}")
            if relevant_docs:
                answer = "I found relevant documents but encountered an error processing them. Please try rephrasing your question."
            else:
                answer = PDF_ONLY_REFUSAL_MESSAGE

        return {
            "answer": answer,
            "conversation_chain": conversation_chain,
            "best_score": best_score,
            "is_hybrid_context": is_hybrid_context,
        }


def build_sources(request, relevant_docs, effective_min_relevance_threshold, answer):
    """Build the response sources from the filtered relevant docs."""
    sources = []
    if request.include_sources and relevant_docs and answer != PDF_ONLY_REFUSAL_MESSAGE:
        seen = set()
        sorted_docs = sorted(relevant_docs, key=lambda x: x[1], reverse=True)
        for doc, score in sorted_docs:
            if score < effective_min_relevance_threshold:
                continue
            md = getattr(doc, "metadata", None) or {}
            src_type = md.get("source_type", "pdf")
            if src_type != "pdf":
                continue
            key = (md.get("pdf_id"), md.get("chunk_id"), md.get("page_number"))
            if key in seen:
                continue
            seen.add(key)
            source_name = md.get("pdf_title", "Unknown PDF")
            sources.append({
                "source_type": "pdf",
                "pdf_title": source_name,
                "pdf_id": md.get("pdf_id"),
                "page_number": md.get("page_number"),
                "chunk_id": md.get("chunk_id"),
                "relevance_score": score,
                "source_name": source_name
            })
    return sources


async def dispatch_tracking(*, request, session_id, answer, query_embedding, sources):
    """Thin wrapper to keep the route orchestration readable."""
    await _dispatch_chat_tracking(
        user_id=request.user_id or "anonymous",
        session_id=session_id,
        query_text=request.query,
        answer=answer,
        query_embedding=query_embedding,
        sources=sources,
    )


def _build_chat_response(*, answer, sources, session_id, processing_time, timestamp=None):
    """Create a ChatResponse while preserving current response fields."""
    payload = dict(
        answer=answer,
        sources=sources,
        conversation_id=session_id,
        processing_time=processing_time,
    )
    if timestamp is not None:
        payload["timestamp"] = timestamp
    else:
        payload["tokens_used"] = None
    return ChatResponse(**payload)


def _follow_up_topic_hint(conversation_chain) -> str:
    return _generation_follow_up_topic_hint(conversation_chain)


def _looks_already_structured(response_text: str) -> bool:
    return _generation_looks_already_structured(response_text)


def _format_educational_response(
    response_text: str,
    query: str,
    has_relevant_docs: bool = True,
    hybrid_weak_context: bool = False,
) -> str:
    return _generation_format_educational_response(
        response_text,
        query,
        has_relevant_docs=has_relevant_docs,
        hybrid_weak_context=hybrid_weak_context,
    )


# Video-based response function removed - PDF-only mode
# Using _generate_clarification_response for all content-based responses


def build_grounded_prompt(
    mode: str,
    context: str,
    query: str,
    *,
    topic_hint: str = "\n",
    is_follow_up: bool = False,
) -> str:
    return _generation_build_grounded_prompt(
        mode,
        context,
        query,
        topic_hint=topic_hint,
        is_follow_up=is_follow_up,
    )


def _generate_clarification_response(query: str, relevant_docs: list) -> str:
    return _generation_generate_clarification_response(query, relevant_docs)


def _generate_weak_hybrid_response(query: str, relevant_docs: list) -> str:
    return _generation_generate_weak_hybrid_response(query, relevant_docs)


def _generate_context_grounded_response(
    query: str,
    context: str,
    *,
    is_hybrid_context: bool = False,
    is_follow_up: bool = False,
    topic_hint: str = "\n",
) -> str:
    return _generation_generate_context_grounded_response(
        query,
        context,
        is_hybrid_context=is_hybrid_context,
        is_follow_up=is_follow_up,
        topic_hint=topic_hint,
    )

# =========================================
# Session Management Endpoints
# =========================================

@router.post("/session/create")
async def create_new_session(request_data: dict = Body(...)):
    """
    Create a new chat session.
    This endpoint MUST be called when:
    - User opens the chatbot for the first time
    - User refreshes the page
    - User closes and reopens the chatbot
    
    This ensures:
    - A unique session_id is generated
    - Clean conversation state for the new session
    
    Args:
        request_data: Dictionary (can be empty, user_id is ignored)
        
    Returns:
        JSON with new session_id
        
    Example:
        POST /chat/session/create
        Body: {}
        Response: {
            "session_id": "uuid-string",
            "created_at": "2025-12-30T18:00:00Z",
            "message": "New session created successfully"
        }
    """
    try:
        # Generate new unique session ID
        new_session_id = str(uuid.uuid4())
        
        # Check if session management is available
        if set_active_session_by_session_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session management service is not available"
            )
        
        # Set the new session as active (using session_id as user_id placeholder)
        # Since we're ignoring user_id, we use the session_id itself as the identifier
        profile_id = set_active_session_by_session_id(new_session_id)
        
        if profile_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
        
        logger.info(f"New session created: {new_session_id}")
        
        return {
            "session_id": new_session_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": "New session created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating new session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating session: {str(e)}"
        )


@router.post("/session/end")
async def end_session(request_data: dict = Body(...)):
    """
    End a chat session.
    This endpoint SHOULD be called when:
    - User closes the chatbot tab/window
    - User logs out
    - User explicitly ends the chat
    
    This ensures:
    - Session is marked as inactive
    - Conversation memory is cleared
    - Resources are freed
    
    Args:
        request_data: Dictionary containing session_id (user_id is ignored)
        
    Returns:
        Success message
        
    Example:
        POST /chat/session/end
        Body: {"session_id": "uuid-string"}
        Response: {
            "message": "Session ended successfully",
            "session_id": "uuid-string"
        }
    """
    try:
        # Validate request - only session_id is required
        if 'session_id' not in request_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: session_id"
            )
        
        session_id = request_data.get('session_id')
        
        # Validate session_id is not empty
        if not session_id or not str(session_id).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="session_id must not be empty"
            )
        
        # Check if session management is available
        if deactivate_session_by_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session management service is not available"
            )
        
        # Deactivate the session in database (using session_id only)
        success = deactivate_session_by_id(session_id)
        
        if not success:
            logger.warning(f"Session {session_id} not found or already inactive")
            # Don't raise error - session might already be inactive
        
        # Clear conversation chain from memory
        _clear_conversation_chain(session_id)
        
        logger.info(f"Session ended: {session_id}")
        
        return {
            "message": "Session ended successfully",
            "session_id": session_id,
            "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error ending session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ending session: {str(e)}"
        )


# Define endpoint - conditionally add response_model to prevent crashes
# FastAPI doesn't accept None for response_model, so we use a wrapper
def _create_query_endpoint():
    """Create the query endpoint with proper response_model handling."""
    if ChatResponse is not None:
        @router.post("/query", response_model=ChatResponse)
        async def query_chat_impl(request_data: dict = Body(...)):
            return await _query_chat_handler(request_data)
        return query_chat_impl
    else:
        @router.post("/query")
        async def query_chat_impl(request_data: dict = Body(...)):
            return await _query_chat_handler(request_data)
        return query_chat_impl

# Register the endpoint
_create_query_endpoint()

async def _query_chat_handler(request_data: dict):
    """
    Internal handler for chat query - separated to allow conditional decorator.
    
    Args:
        request_data: Raw request data from client
        
    Returns:
        ChatResponse with answer and sources
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    
    # Check if critical imports are available with detailed diagnostics
    missing_services = []
    
    if ChatRequest is None or ChatResponse is None:
        logger.error("ChatRequest or ChatResponse is None - schemas failed to import")
        missing_services.append("schemas")
    
    if load_supabase_vectorstore is None:
        logger.error("load_supabase_vectorstore is None - vector_store failed to import")
        missing_services.append("vector_store")
    
    # Check environment variables
    import os
    missing_env_vars = []
    if not os.getenv("OPENAI_API_KEY"):
        missing_env_vars.append("OPENAI_API_KEY")
    if not os.getenv("SUPABASE_URL"):
        missing_env_vars.append("SUPABASE_URL")
    if not os.getenv("SUPABASE_SERVICE_KEY"):
        missing_env_vars.append("SUPABASE_SERVICE_KEY")
    
    if missing_services or missing_env_vars:
        error_detail = {
            "error": "service_unavailable",
            "message": "Chat service is not properly configured. Please check server logs.",
            "missing_services": missing_services,
            "missing_environment_variables": missing_env_vars,
            "import_errors": _import_errors,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%f")
        }
        
        # Provide helpful guidance
        guidance_parts = []
        if missing_env_vars:
            guidance_parts.append(f"Missing required environment variables: {', '.join(missing_env_vars)}. Please configure these in your .env file or Vercel environment variables.")
        if missing_services:
            guidance_parts.append(f"Failed to import services: {', '.join(missing_services)}.")
            # Add specific import error details
            for service in missing_services:
                if service in _import_errors:
                    guidance_parts.append(f"  - {service}: {_import_errors[service]}")
        
        if not guidance_parts:
            guidance_parts.append("This may indicate missing dependencies or configuration issues. Check Vercel deployment logs for details.")
        
        error_detail["guidance"] = " ".join(guidance_parts)
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail
        )
    
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
        
        # =========================================
        # Session Validation & Management
        # =========================================
        
        # Extract session_id (user_id is ignored for session management, kept for chatbot_chat_history)
        user_id = request.user_id or "anonymous"
        session_id = request.conversation_id
        
        # CRITICAL: Always ensure a fresh session on first API call
        # This prevents old data from showing up in new conversations
        if not session_id:
            # No session_id provided - CREATE NEW SESSION (this deactivates all old sessions)
            if set_active_session_by_session_id is not None:
                try:
                    # Generate new session - this will automatically deactivate old sessions
                    new_session_id = str(uuid.uuid4())
                    
                    # Clear any existing conversation chain for this new session to ensure fresh start
                    _clear_conversation_chain(new_session_id)
                    
                    profile_id = set_active_session_by_session_id(new_session_id)
                    
                    if profile_id:
                        session_id = new_session_id
                        # Update request conversation_id for downstream use
                        request.conversation_id = new_session_id
                        logger.info(f"Auto-created NEW session: {new_session_id} (old sessions deactivated, conversation chain cleared)")
                    else:
                        # Fallback if session creation fails
                        session_id = str(uuid.uuid4())
                        request.conversation_id = session_id
                        logger.warning(f"Session creation returned None, using fallback: {session_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-create session: {e}")
                    # Fallback: create session ID but can't register it
                    session_id = str(uuid.uuid4())
                    request.conversation_id = session_id
            else:
                # Session management not available - just generate ID
                session_id = str(uuid.uuid4())
                request.conversation_id = session_id
        
        elif session_id:
            # Session_id provided - validate it's active
            if is_session_active is not None:
                try:
                    session_is_active = is_session_active(session_id)
                    
                    if not session_is_active:
                        # Session is not active - CREATE NEW SESSION to prevent old data
                        logger.warning(f"Session {session_id} is not active - creating new session")
                        try:
                            # Clear old conversation chain for the inactive session
                            _clear_conversation_chain(session_id)
                            
                            # Generate new session ID
                            new_session_id = str(uuid.uuid4())
                            
                            # Clear conversation chain for new session to ensure fresh start
                            _clear_conversation_chain(new_session_id)
                            
                            profile_id = set_active_session_by_session_id(new_session_id)
                            if profile_id:
                                session_id = new_session_id
                                request.conversation_id = new_session_id
                                logger.info(f"Created new active session: {new_session_id} (old session {session_id} cleared)")
                            else:
                                logger.warning(f"Failed to create new session, using provided: {session_id}")
                        except Exception as e:
                            logger.error(f"Error creating new session: {e}")
                            # Continue with provided session_id but log warning
                    else:
                        # Session is valid - log and proceed
                        if settings.is_development:
                            logger.info(f"Session validated: {session_id}")
                        
                except HTTPException:
                    raise
                except Exception as session_error:
                    logger.error(f"Error validating session: {session_error}")
                    # Don't block the query if validation fails - fail open for robustness
                    logger.warning("Session validation failed - proceeding with query")
        
        
        # =========================================
        # Query Processing
        # =========================================
        
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
                "Hey! I'm here to help you understand your PDF content. What would you like to learn about?",
                "Hello! Welcome to your study companion. I can help you find information in your uploaded materials. What interests you?",
                "Hi! I'm your educational assistant. Ready to dive into your learning materials — what's on your mind?"
            ]
            import random
            answer = random.choice(greeting_responses)
            session_id = request.conversation_id or str(uuid.uuid4())

            await dispatch_tracking(
                request=request,
                session_id=session_id,
                answer=answer,
                query_embedding=None,
                sources=[],
            )

            return _build_chat_response(
                answer=answer,
                sources=[],
                session_id=session_id,
                processing_time=0.1,
                timestamp=time.time(),
            )

        # Initialize answer and sources early to ensure they're always defined
        answer = "I'm sorry, but I encountered an error processing your query. Please try again."
        sources = []
        session_id = request.conversation_id or str(uuid.uuid4())
        query_embedding = None
        
        vs = _load_vector_store()

        # First, perform similarity search to check if relevant content exists
        try:
            embedding_result = handle_query_embedding(request, vs)
            session_id = embedding_result["session_id"]
            is_follow_up = embedding_result["is_follow_up"]
            conversation_chain = embedding_result["conversation_chain"]
            query_embedding = embedding_result["query_embedding"]

            retrieval_result = handle_retrieval(request, vs, query_embedding)
            docs_with_scores = retrieval_result["docs_with_scores"]
            retrieval_best = retrieval_result["retrieval_best"]
            retrieval_used_degraded_fallback = retrieval_result["retrieval_used_degraded_fallback"]
            effective_min_relevance_threshold = retrieval_result["effective_min_relevance_threshold"]
            effective_high_confidence_score = retrieval_result["effective_high_confidence_score"]

            if settings.is_development and retrieval_used_degraded_fallback:
                logger.warning(
                    "Retrieval is using DEGRADED fallback candidates; applying stricter gating "
                    "(min=%.2f, strong=%.2f) to avoid random answers.",
                    effective_min_relevance_threshold,
                    effective_high_confidence_score,
                )

            gating_result = apply_gating_logic(
                docs_with_scores,
                retrieval_best,
                effective_min_relevance_threshold,
                effective_high_confidence_score,
            )
            relevant_docs = gating_result["relevant_docs"]

            if gating_result["should_refuse"]:
                answer = gating_result["answer"]
                sources = gating_result["sources"]
            else:
                generation_result = generate_answer(
                    request,
                    relevant_docs,
                    retrieval_best,
                    effective_high_confidence_score,
                    conversation_chain,
                    session_id,
                    vs,
                    is_follow_up,
                )
                answer = generation_result["answer"]
                sources = build_sources(
                    request,
                    relevant_docs,
                    effective_min_relevance_threshold,
                    answer,
                )
            
        except HTTPException:
            # Re-raise HTTPExceptions (like embedding errors) so they're properly handled
            raise
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            logger.exception(f"Error during similarity search: {type(e).__name__}: {error_msg}")
            logger.error(f"Full traceback: {error_traceback}")
            
            # Provide a helpful error message instead of generic one
            if "api key" in error_msg.lower() or "401" in error_msg or "invalid" in error_msg.lower():
                answer = "I'm unable to process your query because the OpenAI API key is invalid or expired. Please check your API configuration."
            elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                answer = "I'm currently unable to connect to the knowledge base. Please try again in a moment."
            else:
                answer = f"I encountered an error while processing your query: {error_msg}"
            
            sources = []
        
        processing_time = time.time() - start_time
        
        await dispatch_tracking(
            request=request,
            session_id=session_id,
            answer=answer,
            query_embedding=query_embedding,
            sources=sources,
        )

        return _build_chat_response(
            answer=answer,
            sources=sources,
            session_id=session_id,
            processing_time=round(processing_time, 3),
        )
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.exception(f"Unexpected error in query_chat: {type(e).__name__}: {error_msg}")
        logger.error(f"Full traceback: {error_traceback}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {error_msg}"
        )


@router.get("/history/{session_id}")
async def get_session_chat_history(
    session_id: str,
    limit: int = 50
):
    """
    Retrieve chat history for a specific session (session_id only, user_id ignored).
    This ensures only data from the specified session is returned, preventing old data from appearing.
    
    Args:
        session_id: Session identifier (required)
        limit: Maximum number of records to return
        
    Returns:
        List of chat history records for this session only
    """
    try:
        if not session_id or not str(session_id).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required"
            )
        
        # Use session_id-only function to ensure isolation
        if get_chat_history_by_session is not None:
            history = get_chat_history_by_session(session_id, limit)
        else:
            # Fallback to old method if new function not available
            history = get_chat_history("anonymous", session_id, limit) if get_chat_history else []
        
        return {
            "session_id": session_id,
            "history": history,
            "count": len(history),
            "message": "Only data from this session is returned"
        }
    except HTTPException:
        raise
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



