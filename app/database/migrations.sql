-- =========================================
-- Chatbot Database Schema (reads from Assessment pdf_embeddings)
-- Does NOT create or alter Assessment tables: pdf_documents, pdf_embeddings, pdf_processing_log
-- Chatbot tables: chatbot_user_queries, chatbot_chat_history, chatbot_user_profile only
-- Vector search reads from Assessment.pdf_embeddings via RPCs with column mapping
-- =========================================

-- =========================================
-- Extensions
-- =========================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================
-- Core Tables (Chatbot only - no pdf_embeddings table here)
-- =========================================

-- 1. User Queries Table
CREATE TABLE IF NOT EXISTS chatbot_user_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),
    matched_chunk_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Persisted conversation turns
CREATE TABLE IF NOT EXISTS public.chatbot_chat_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text,
    session_id text,
    user_message text NOT NULL,
    bot_response text,
    created_at timestamptz DEFAULT now()
);

-- 3. User Profile Table
CREATE TABLE IF NOT EXISTS public.chatbot_user_profile (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    session_id text NOT NULL,
    is_active boolean DEFAULT TRUE,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT chatbot_user_profile_session_id_unique UNIQUE (session_id)
);

-- =========================================
-- Indexes for Performance (chatbot tables only)
-- =========================================

-- User Queries Indexes
CREATE INDEX IF NOT EXISTS chatbot_user_queries_embedding_idx
ON chatbot_user_queries USING ivfflat (query_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chatbot_user_queries_user_id_idx
ON chatbot_user_queries (user_id);

-- Chat History Indexes
CREATE INDEX IF NOT EXISTS chatbot_chat_history_user_idx ON public.chatbot_chat_history (user_id);
CREATE INDEX IF NOT EXISTS chatbot_chat_history_created_at_idx ON public.chatbot_chat_history (created_at DESC);

-- User Profile Indexes
CREATE INDEX IF NOT EXISTS chatbot_user_profile_user_id_idx ON public.chatbot_user_profile (user_id);
CREATE INDEX IF NOT EXISTS chatbot_user_profile_session_id_idx ON public.chatbot_user_profile (session_id);
CREATE INDEX IF NOT EXISTS chatbot_user_profile_active_session_idx
ON public.chatbot_user_profile (user_id)
WHERE is_active = TRUE;

-- =========================================
-- Vector search: read from Assessment pdf_embeddings (chunk_text, chunk_index)
-- Mapping: content = chunk_text, chunk_id = chunk_index. Do NOT modify Assessment schema.
-- =========================================

DROP FUNCTION IF EXISTS public.match_pdf_embeddings(vector, int) CASCADE;
DROP FUNCTION IF EXISTS match_pdf_embeddings(vector, float, int) CASCADE;

-- RPC: vector similarity search on Assessment pdf_embeddings; returns chatbot-expected shape
CREATE OR REPLACE FUNCTION public.match_pdf_embeddings(
  query_embedding vector(1536),
  match_count int
)
RETURNS TABLE (
    content TEXT,
    pdf_id TEXT,
    pdf_title TEXT,
    chunk_id INTEGER,
    page_number INTEGER,
    similarity FLOAT
)
LANGUAGE sql
AS $$
  SELECT
    pe.chunk_text AS content,
    pe.pdf_id,
    pe.pdf_title,
    pe.chunk_index AS chunk_id,
    pe.page_number,
    1 - (pe.embedding <=> query_embedding) AS similarity
  FROM public.pdf_embeddings pe
  ORDER BY pe.embedding <=> query_embedding ASC
  LIMIT LEAST(match_count, 200);
$$;

-- =========================================
-- Session Management Functions
-- =========================================

CREATE OR REPLACE FUNCTION set_active_session(
    p_user_id TEXT,
    p_session_id TEXT
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_id uuid;
BEGIN
    UPDATE public.chatbot_user_profile
    SET is_active = FALSE,
        updated_at = now()
    WHERE user_id = p_user_id
      AND is_active = TRUE;

    SELECT id INTO v_profile_id
    FROM public.chatbot_user_profile
    WHERE user_id = p_user_id
      AND session_id = p_session_id;

    IF v_profile_id IS NOT NULL THEN
        UPDATE public.chatbot_user_profile
        SET is_active = TRUE,
            updated_at = now()
        WHERE id = v_profile_id;
    ELSE
        INSERT INTO public.chatbot_user_profile (user_id, session_id, is_active, created_at, updated_at)
        VALUES (p_user_id, p_session_id, TRUE, now(), now())
        RETURNING id INTO v_profile_id;
    END IF;

    RETURN v_profile_id;
END;
$$;

CREATE OR REPLACE FUNCTION get_active_session(p_user_id TEXT)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_session_id TEXT;
BEGIN
    SELECT session_id INTO v_session_id
    FROM public.chatbot_user_profile
    WHERE user_id = p_user_id
      AND is_active = TRUE
    LIMIT 1;

    RETURN v_session_id;
END;
$$;

CREATE OR REPLACE FUNCTION update_user_profile_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_profile_updated_at_trigger ON public.chatbot_user_profile;
CREATE TRIGGER user_profile_updated_at_trigger
    BEFORE UPDATE ON public.chatbot_user_profile
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profile_updated_at();

-- =========================================
-- Permissions
-- =========================================
GRANT USAGE ON SCHEMA public TO anon, authenticated;

GRANT ALL ON chatbot_user_queries TO anon, authenticated;
GRANT ALL ON public.chatbot_chat_history TO anon, authenticated;
GRANT ALL ON public.chatbot_user_profile TO anon, authenticated;

GRANT EXECUTE ON FUNCTION public.match_pdf_embeddings(vector, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION set_active_session(TEXT, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_active_session(TEXT) TO anon, authenticated;
