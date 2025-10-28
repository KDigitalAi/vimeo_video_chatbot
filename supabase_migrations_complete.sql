-- =========================================
-- Complete Supabase Database Schema for Vimeo Video Chatbot
-- Includes: Video embeddings, PDF embeddings, Chat history, and Unified search
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
    matched_video_id TEXT,
    matched_chunk_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Video Embeddings Table (assumed to exist)
-- This table should already exist from your video processing
-- If not, create it with:
-- CREATE TABLE IF NOT EXISTS video_embeddings (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     content TEXT NOT NULL,
--     embedding vector(1536),
--     video_id TEXT NOT NULL,
--     video_title TEXT,
--     chunk_id TEXT,
--     timestamp_start FLOAT,
--     timestamp_end FLOAT,
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
-- );

-- 3. PDF Embeddings Table
CREATE TABLE IF NOT EXISTS pdf_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    pdf_id TEXT NOT NULL,
    pdf_title TEXT,
    chunk_id TEXT,
    page_number INTEGER,
    source_type TEXT DEFAULT 'pdf',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Chat History Table
CREATE TABLE IF NOT EXISTS public.chat_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text,
    session_id text,
    user_message text NOT NULL,
    bot_response text,
    video_id text,
    created_at timestamptz DEFAULT now()
);

-- =========================================
-- Indexes for Performance
-- =========================================

-- User Queries Indexes
CREATE INDEX IF NOT EXISTS user_queries_embedding_idx 
ON user_queries USING ivfflat (query_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS user_queries_user_id_idx 
ON user_queries (user_id);

-- Video Embeddings Indexes
CREATE INDEX IF NOT EXISTS video_embeddings_embedding_idx 
ON video_embeddings USING ivfflat (embedding vector_cosine_ops);

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

-- =========================================
-- Search Functions
-- =========================================

-- Video-only search function
CREATE OR REPLACE FUNCTION match_video_embeddings(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    video_id TEXT,
    video_title TEXT,
    chunk_id TEXT,
    timestamp_start FLOAT,
    timestamp_end FLOAT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ve.id,
        ve.content,
        ve.embedding,
        ve.video_id,
        ve.video_title,
        ve.chunk_id,
        ve.timestamp_start,
        ve.timestamp_end,
        1 - (ve.embedding <=> query_embedding) as similarity
    FROM video_embeddings ve
    WHERE 1 - (ve.embedding <=> query_embedding) > match_threshold
    ORDER BY ve.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Simple video search function (PostgREST compatible)
CREATE OR REPLACE FUNCTION public.match_video_embeddings(
  query_embedding vector(1536),
  match_count int
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    video_id TEXT,
    video_title TEXT,
    chunk_id TEXT,
    timestamp_start FLOAT,
    timestamp_end FLOAT,
    similarity FLOAT
)
LANGUAGE sql
AS $$
  SELECT 
    ve.id,
    ve.content,
    ve.embedding,
    ve.video_id,
    ve.video_title,
    ve.chunk_id,
    ve.timestamp_start,
    ve.timestamp_end,
    1 - (ve.embedding <=> query_embedding) as similarity
  FROM public.video_embeddings ve
  WHERE 1 - (ve.embedding <=> query_embedding) > 0.2
  ORDER BY ve.embedding <=> query_embedding ASC
  LIMIT LEAST(match_count, 200);
$$;

-- Unified search function (videos + PDFs)
CREATE OR REPLACE FUNCTION match_unified_embeddings(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    source_id TEXT,
    source_title TEXT,
    chunk_id TEXT,
    source_type TEXT,
    timestamp_start FLOAT,
    timestamp_end FLOAT,
    page_number INTEGER,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    (
        -- Video embeddings
        SELECT 
            ve.id,
            ve.content,
            ve.embedding,
            ve.video_id as source_id,
            ve.video_title as source_title,
            ve.chunk_id,
            'video' as source_type,
            ve.timestamp_start,
            ve.timestamp_end,
            NULL as page_number,
            1 - (ve.embedding <=> query_embedding) as similarity
        FROM video_embeddings ve
        WHERE 1 - (ve.embedding <=> query_embedding) > match_threshold
        
        UNION ALL
        
        -- PDF embeddings
        SELECT 
            pe.id,
            pe.content,
            pe.embedding,
            pe.pdf_id as source_id,
            pe.pdf_title as source_title,
            pe.chunk_id,
            pe.source_type,
            NULL as timestamp_start,
            NULL as timestamp_end,
            pe.page_number,
            1 - (pe.embedding <=> query_embedding) as similarity
        FROM pdf_embeddings pe
        WHERE 1 - (pe.embedding <=> query_embedding) > match_threshold
    )
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Simple unified search function (PostgREST compatible)
CREATE OR REPLACE FUNCTION public.match_unified_embeddings(
    query_embedding vector(1536),
    match_count int
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    embedding vector(1536),
    source_id TEXT,
    source_title TEXT,
    chunk_id TEXT,
    source_type TEXT,
    timestamp_start FLOAT,
    timestamp_end FLOAT,
    page_number INTEGER,
    similarity FLOAT
)
LANGUAGE sql
AS $$
    (
        -- Video embeddings
        SELECT 
            ve.id,
            ve.content,
            ve.embedding,
            ve.video_id as source_id,
            ve.video_title as source_title,
            ve.chunk_id,
            'video' as source_type,
            ve.timestamp_start,
            ve.timestamp_end,
            NULL as page_number,
            1 - (ve.embedding <=> query_embedding) as similarity
        FROM public.video_embeddings ve
        WHERE 1 - (ve.embedding <=> query_embedding) > 0.2
        
        UNION ALL
        
        -- PDF embeddings
        SELECT 
            pe.id,
            pe.content,
            pe.embedding,
            pe.pdf_id as source_id,
            pe.pdf_title as source_title,
            pe.chunk_id,
            pe.source_type,
            NULL as timestamp_start,
            NULL as timestamp_end,
            pe.page_number,
            1 - (pe.embedding <=> query_embedding) as similarity
        FROM public.pdf_embeddings pe
        WHERE 1 - (pe.embedding <=> query_embedding) > 0.2
    )
    ORDER BY similarity ASC
    LIMIT LEAST(match_count, 200);
$$;

-- LangChain compatibility function
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
    ve.id,
    ve.content,
    jsonb_build_object(
      'video_id', ve.video_id,
      'video_title', ve.video_title,
      'chunk_id', ve.chunk_id,
      'timestamp_start', ve.timestamp_start,
      'timestamp_end', ve.timestamp_end
    ) as metadata,
    1 - (ve.embedding <=> query_embedding) as similarity
  FROM public.video_embeddings ve
  WHERE 1 - (ve.embedding <=> query_embedding) > 0.7
  ORDER BY ve.embedding <=> query_embedding ASC
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
    embedding_count BIGINT,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
AS $$
    SELECT 
        pe.pdf_id,
        pe.pdf_title,
        COUNT(*) as embedding_count,
        MIN(pe.created_at) as created_at
    FROM pdf_embeddings pe
    GROUP BY pe.pdf_id, pe.pdf_title
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
-- Permissions
-- =========================================
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Table permissions
GRANT ALL ON user_queries TO anon, authenticated;
GRANT ALL ON video_embeddings TO anon, authenticated;
GRANT ALL ON pdf_embeddings TO anon, authenticated;
GRANT ALL ON public.chat_history TO anon, authenticated;

-- Function permissions
GRANT EXECUTE ON FUNCTION match_video_embeddings TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_video_embeddings TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_unified_embeddings TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_unified_embeddings TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_documents TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_pdf_documents TO anon, authenticated;
GRANT EXECUTE ON FUNCTION delete_pdf_document TO anon, authenticated;

-- =========================================
-- Migration Complete
-- =========================================
-- This file contains all database schema for the Vimeo Video Chatbot
-- including video embeddings, PDF embeddings, chat history, and unified search
