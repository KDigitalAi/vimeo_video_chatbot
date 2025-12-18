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
-- Permissions
-- =========================================
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Table permissions
GRANT ALL ON user_queries TO anon, authenticated;
GRANT ALL ON pdf_embeddings TO anon, authenticated;
GRANT ALL ON public.chat_history TO anon, authenticated;

-- Function permissions
GRANT EXECUTE ON FUNCTION public.match_pdf_embeddings(vector, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_pdf_embeddings(vector, float, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_documents(vector, int, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_pdf_documents TO anon, authenticated;
GRANT EXECUTE ON FUNCTION delete_pdf_document TO anon, authenticated;

-- =========================================
-- Migration Complete
-- =========================================
-- This file contains all database schema for the PDF Knowledge Chatbot
-- including PDF embeddings, chat history, and PDF search functions
