-- Supabase migrations for user_queries table and vector similarity search
-- Run these SQL commands in your Supabase SQL editor

-- 1. Create user_queries table
CREATE TABLE IF NOT EXISTS user_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),
    matched_video_id TEXT,
    matched_chunk_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Create indexes for user_queries
CREATE INDEX IF NOT EXISTS user_queries_embedding_idx 
ON user_queries USING ivfflat (query_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS user_queries_user_id_idx 
ON user_queries (user_id);

-- 3. Ensure video_embeddings table has proper vector index
CREATE INDEX IF NOT EXISTS video_embeddings_embedding_idx 
ON video_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 4. Create RPC function for vector similarity search
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

-- 5. Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON user_queries TO anon, authenticated;
GRANT ALL ON video_embeddings TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_video_embeddings TO anon, authenticated;

-- =========================================
-- Ensure pgvector extension exists
-- =========================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================
-- Simple match function compatible with PostgREST RPC
-- Returns rows from public.video_embeddings ordered by distance
-- =========================================
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
  WHERE 1 - (ve.embedding <=> query_embedding) > 0.2  -- Lower threshold to get more results
  ORDER BY ve.embedding <=> query_embedding ASC
  LIMIT LEAST(match_count, 200);
$$;

-- =========================================
-- Chat History Table for Vimeo Video Chatbot
-- =========================================
CREATE TABLE IF NOT EXISTS public.chat_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text,
  session_id text,
  user_message text NOT NULL,
  bot_response text,
  video_id text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_history_user_idx ON public.chat_history (user_id);
CREATE INDEX IF NOT EXISTS chat_history_created_at_idx ON public.chat_history (created_at DESC);

-- Grant permissions for chat_history table
GRANT ALL ON public.chat_history TO anon, authenticated;

-- =========================================
-- Create match_documents function for LangChain compatibility
-- =========================================
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

-- Grant execute permission on match_documents function
GRANT EXECUTE ON FUNCTION public.match_documents TO anon, authenticated;