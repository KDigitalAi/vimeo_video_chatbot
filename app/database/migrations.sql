-- =========================================
-- Complete Supabase Database Schema for PDF Knowledge Chatbot
-- Includes: PDF embeddings, Chat history, and PDF search
-- Run these SQL commands in your Supabase SQL editor
-- =========================================

-- =========================================
-- Extensions
-- =========================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================
-- Core Tables
-- =========================================

-- 1. User Queries Table
CREATE TABLE IF NOT EXISTS user_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),
    matched_chunk_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. PDF Embeddings Table
CREATE TABLE IF NOT EXISTS pdf_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    folder TEXT,
    pdf_id TEXT NOT NULL,
    pdf_title TEXT,
    chunk_id TEXT,
    page_number INTEGER,
    source_type TEXT DEFAULT 'pdf',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Chat History Table
CREATE TABLE IF NOT EXISTS public.chat_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text,
    session_id text,
    user_message text NOT NULL,
    bot_response text,
    created_at timestamptz DEFAULT now()
);

-- 4. User Profile Table
CREATE TABLE IF NOT EXISTS public.user_profile (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    session_id text NOT NULL,
    is_active boolean DEFAULT TRUE,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT user_profile_session_id_unique UNIQUE (session_id)
);

-- =========================================
-- Migration: Add missing columns to pdf_embeddings
-- =========================================
ALTER TABLE pdf_embeddings
ADD COLUMN IF NOT EXISTS folder TEXT;

ALTER TABLE pdf_embeddings
ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'pdf';

-- =========================================
-- Indexes for Performance
-- =========================================

-- User Queries Indexes
CREATE INDEX IF NOT EXISTS user_queries_embedding_idx 
ON user_queries USING ivfflat (query_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS user_queries_user_id_idx 
ON user_queries (user_id);

-- PDF Embeddings Indexes
CREATE INDEX IF NOT EXISTS pdf_embeddings_embedding_idx 
ON pdf_embeddings USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS pdf_embeddings_pdf_id_idx 
ON pdf_embeddings (pdf_id);

CREATE INDEX IF NOT EXISTS pdf_embeddings_source_type_idx 
ON pdf_embeddings (source_type);

CREATE INDEX IF NOT EXISTS pdf_embeddings_created_at_idx 
ON pdf_embeddings (created_at DESC);

-- Chat History Indexes
CREATE INDEX IF NOT EXISTS chat_history_user_idx ON public.chat_history (user_id);
CREATE INDEX IF NOT EXISTS chat_history_created_at_idx ON public.chat_history (created_at DESC);

-- User Profile Indexes
CREATE INDEX IF NOT EXISTS user_profile_user_id_idx ON public.user_profile (user_id);
CREATE INDEX IF NOT EXISTS user_profile_session_id_idx ON public.user_profile (session_id);
-- Partial index for fast lookup of active sessions per user
CREATE INDEX IF NOT EXISTS user_profile_active_session_idx 
ON public.user_profile (user_id) 
WHERE is_active = TRUE;

-- =========================================
-- Search Functions
-- =========================================

-- Drop existing functions if they exist (to handle signature changes)
DROP FUNCTION IF EXISTS public.match_pdf_embeddings(vector, int) CASCADE;
DROP FUNCTION IF EXISTS match_pdf_embeddings(vector, float, int) CASCADE;
DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb) CASCADE;

-- PDF search function (PostgREST compatible)
CREATE OR REPLACE FUNCTION public.match_pdf_embeddings(
  query_embedding vector(1536),
  match_count int
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    pdf_id TEXT,
    pdf_title TEXT,
    chunk_id TEXT,
    page_number INTEGER,
    folder TEXT,
    source_type TEXT,
    similarity FLOAT
)
LANGUAGE sql
AS $$
  SELECT 
    pe.id,
    pe.content,
    pe.embedding,
    pe.pdf_id,
    pe.pdf_title,
    pe.chunk_id,
    pe.page_number,
    pe.folder,
    pe.source_type,
    1 - (pe.embedding <=> query_embedding) as similarity
  FROM public.pdf_embeddings pe
  WHERE 1 - (pe.embedding <=> query_embedding) > 0.2
  ORDER BY pe.embedding <=> query_embedding ASC
  LIMIT LEAST(match_count, 200);
$$;

-- PDF search function with threshold (for advanced use)
CREATE OR REPLACE FUNCTION match_pdf_embeddings(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    pdf_id TEXT,
    pdf_title TEXT,
    chunk_id TEXT,
    page_number INTEGER,
    folder TEXT,
    source_type TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pe.id,
        pe.content,
        pe.embedding,
        pe.pdf_id,
        pe.pdf_title,
        pe.chunk_id,
        pe.page_number,
        pe.folder,
        pe.source_type,
        1 - (pe.embedding <=> query_embedding) as similarity
    FROM pdf_embeddings pe
    WHERE 1 - (pe.embedding <=> query_embedding) > match_threshold
    ORDER BY pe.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- LangChain compatibility function (PDF-only)
CREATE OR REPLACE FUNCTION public.match_documents(
  query_embedding vector(1536),
  match_count int DEFAULT 5,
  filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    pe.id,
    pe.content,
    jsonb_build_object(
      'pdf_id', pe.pdf_id,
      'pdf_title', pe.pdf_title,
      'chunk_id', pe.chunk_id,
      'page_number', pe.page_number,
      'folder', pe.folder,
      'source_type', pe.source_type
    ) as metadata,
    1 - (pe.embedding <=> query_embedding) as similarity
  FROM public.pdf_embeddings pe
  WHERE 1 - (pe.embedding <=> query_embedding) > 0.7
  ORDER BY pe.embedding <=> query_embedding ASC
  LIMIT LEAST(match_count, 200);
END;
$$;

-- =========================================
-- PDF Management Functions
-- =========================================

-- Function to get PDF document list
CREATE OR REPLACE FUNCTION get_pdf_documents()
RETURNS TABLE (
    pdf_id TEXT,
    pdf_title TEXT,
    folder TEXT,
    embedding_count BIGINT,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
AS $$
    SELECT 
        pe.pdf_id,
        pe.pdf_title,
        pe.folder,
        COUNT(*) as embedding_count,
        MIN(pe.created_at) as created_at
    FROM pdf_embeddings pe
    GROUP BY pe.pdf_id, pe.pdf_title, pe.folder
    ORDER BY created_at DESC;
$$;

-- Function to delete PDF and all its embeddings
CREATE OR REPLACE FUNCTION delete_pdf_document(pdf_id_to_delete TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM pdf_embeddings 
    WHERE pdf_id = pdf_id_to_delete;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- =========================================
-- Session Management Functions
-- =========================================

-- Function to set active session for a user
-- This function ensures only ONE active session per user at a time
-- When a new session is created, all previous sessions for that user are deactivated
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
    -- First, deactivate all existing sessions for this user
    UPDATE public.user_profile
    SET is_active = FALSE,
        updated_at = now()
    WHERE user_id = p_user_id
      AND is_active = TRUE;
    
    -- Check if this session already exists
    SELECT id INTO v_profile_id
    FROM public.user_profile
    WHERE user_id = p_user_id
      AND session_id = p_session_id;
    
    IF v_profile_id IS NOT NULL THEN
        -- Update existing session to be active
        UPDATE public.user_profile
        SET is_active = TRUE,
            updated_at = now()
        WHERE id = v_profile_id;
    ELSE
        -- Insert new active session
        INSERT INTO public.user_profile (user_id, session_id, is_active, created_at, updated_at)
        VALUES (p_user_id, p_session_id, TRUE, now(), now())
        RETURNING id INTO v_profile_id;
    END IF;
    
    RETURN v_profile_id;
END;
$$;

-- Function to get active session for a user
-- Returns the current active session_id for a given user_id
CREATE OR REPLACE FUNCTION get_active_session(p_user_id TEXT)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_session_id TEXT;
BEGIN
    SELECT session_id INTO v_session_id
    FROM public.user_profile
    WHERE user_id = p_user_id
      AND is_active = TRUE
    LIMIT 1;
    
    RETURN v_session_id;
END;
$$;

-- Trigger function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profile_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Create trigger to auto-update updated_at on user_profile updates
DROP TRIGGER IF EXISTS user_profile_updated_at_trigger ON public.user_profile;
CREATE TRIGGER user_profile_updated_at_trigger
    BEFORE UPDATE ON public.user_profile
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profile_updated_at();

-- =========================================
-- Permissions
-- =========================================
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Table permissions
GRANT ALL ON user_queries TO anon, authenticated;
GRANT ALL ON pdf_embeddings TO anon, authenticated;
GRANT ALL ON public.chat_history TO anon, authenticated;
GRANT ALL ON public.user_profile TO anon, authenticated;

-- Function permissions
GRANT EXECUTE ON FUNCTION public.match_pdf_embeddings(vector, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_pdf_embeddings(vector, float, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_documents(vector, int, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_pdf_documents TO anon, authenticated;
GRANT EXECUTE ON FUNCTION delete_pdf_document TO anon, authenticated;
GRANT EXECUTE ON FUNCTION set_active_session(TEXT, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_active_session(TEXT) TO anon, authenticated;

-- =========================================
-- Migration Complete
-- =========================================
-- This file contains all database schema for the PDF Knowledge Chatbot
-- including PDF embeddings, chat history, user profiles, and PDF search functions
--
-- Tables:
-- 1. user_queries - Stores user query embeddings and matched chunks
-- 2. pdf_embeddings - Stores PDF content embeddings for vector search
-- 3. chat_history - Stores chat interactions between users and the bot
-- 4. user_profile - Manages users and their active sessions with proper isolation
--
-- Session Management:
-- - Only ONE active session per user is allowed at any time
-- - Use set_active_session(user_id, session_id) to create/activate sessions
-- - Previous sessions are automatically deactivated when a new one is created
-- - Session isolation is guaranteed at the database level
