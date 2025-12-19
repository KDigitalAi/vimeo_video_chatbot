# 🎥 Vimeo Video Chatbot

A production-ready RAG (Retrieval-Augmented Generation) chatbot that enables natural language queries about Vimeo training videos and PDF documents. Built with FastAPI, LangChain, OpenAI embeddings, and Supabase vector storage.

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Application Workflows](#application-workflows)
- [API Documentation](#api-documentation)
- [Environment Configuration](#environment-configuration)
- [Local Development Setup](#local-development-setup)
- [Deployment](#deployment)
- [Logging & Debugging](#logging--debugging)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

### What It Does

The Vimeo Video Chatbot is a full-stack RAG application that:

1. **Ingests Content**: Processes Vimeo videos and PDF documents into searchable embeddings
2. **Enables Queries**: Answers natural language questions about ingested content
3. **Maintains Context**: Preserves conversation history for follow-up questions
4. **Provides Sources**: Returns relevant video timestamps and PDF page references

### Who It's For

- **Educational Institutions**: Students can query course materials (videos + PDFs)
- **Training Organizations**: Employees can search training content
- **Content Creators**: Build searchable knowledge bases from video content
- **Developers**: Reference implementation for RAG applications

### Key Use Cases

- "What does this video teach about machine learning?"
- "Show me examples of React hooks from the training materials"
- "Explain the concept covered at 5:30 in the video"
- "What PDFs discuss authentication best practices?"

---

## Key Features

### ✅ RAG-Based Chat
- Natural language queries about video and PDF content
- Context-aware responses using LangChain ConversationalRetrievalChain
- Conversation memory for follow-up questions
- Source attribution with timestamps and page numbers

### ✅ Video Ingestion
- Automatic Vimeo video processing via API or webhooks
- Caption extraction (primary method)
- Whisper transcription fallback
- Chunking with metadata (video_id, timestamps, titles)
- Duplicate detection and force-reprocess option

### ✅ PDF Ingestion
- Upload and process PDF documents
- Text extraction using PyMuPDF (primary) or PyPDF2 (fallback)
- Page-level chunking with metadata
- Batch upload support
- Duplicate detection

### ✅ Embeddings & Vector Search
- OpenAI `text-embedding-3-small` for embeddings (1536 dimensions)
- Supabase PostgreSQL with pgvector extension
- Cosine similarity search across videos and PDFs
- Dynamic threshold filtering (high/low confidence)
- Unified search across multiple content types

### ✅ Conversation Memory
- Session-based conversation tracking
- Chat history storage in Supabase
- Follow-up question detection
- Context retrieval from previous exchanges

### ✅ Error Handling & Logging
- Comprehensive exception handlers
- Memory usage monitoring and cleanup
- Structured logging to stdout (Vercel-compatible)
- Graceful degradation on service failures

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Frontend SPA  │  (Vanilla JavaScript)
│  (index.html)   │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────────────┐
│      FastAPI Backend                │
│  ┌───────────────────────────────┐  │
│  │  API Routes                   │  │
│  │  - /chat/query                │  │
│  │  - /ingest/video/{video_id}   │  │
│  │  - /pdf/pdf                   │  │
│  │  - /webhooks/vimeo            │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Business Logic Modules        │  │
│  │  - embedding_manager           │  │
│  │  - vector_store                │  │
│  │  - retriever_chain             │  │
│  │  - chat_history_manager        │  │
│  └───────────────────────────────┘  │
└────────┬─────────────────────────────┘
         │
         ├─────────────────┬─────────────────┐
         ▼                 ▼                 ▼
    ┌─────────┐      ┌──────────┐      ┌──────────┐
    │ OpenAI  │      │ Supabase │      │  Vimeo   │
    │  API    │      │ (pgvector)│      │   API    │
    └─────────┘      └──────────┘      └──────────┘
```

### Component Layers

1. **Frontend Layer** (`frontend/`)
   - Vanilla JavaScript SPA
   - No build step required
   - Served by FastAPI static file handler
   - Client-side API calls with `fetch()`

2. **API Layer** (`backend/api/`)
   - FastAPI route handlers
   - Request validation with Pydantic
   - Error handling and response formatting

3. **Business Logic Layer** (`backend/modules/`)
   - Embedding generation (`embedding_manager.py`)
   - Vector search (`vector_store.py`, `vector_store_direct.py`)
   - RAG chain (`retriever_chain.py`)
   - Content processing (`text_processor.py`, `pdf_processor.py`)
   - External integrations (`vimeo_loader.py`, `whisper_transcriber.py`)

4. **Data Layer** (`backend/core/`)
   - Settings management (`settings.py`)
   - Database client (`supabase_client.py`)
   - Data validation (`validation.py`)

5. **Storage Layer** (Supabase)
   - `video_embeddings` table (vector(1536))
   - `pdf_embeddings` table (vector(1536))
   - `chat_history` table
   - `user_queries` table

---

## Project Structure

```
vimeo_video_chatbot/
├── api/                              # Vercel serverless entry point
│   └── index.py                      # Thin wrapper: from backend.main import app
│
├── backend/                          # FastAPI application
│   ├── api/                          # API route handlers
│   │   ├── chat.py                   # Chat query endpoints
│   │   ├── ingest.py                 # Video ingestion endpoints
│   │   ├── pdf_ingest.py             # PDF ingestion endpoints
│   │   └── webhooks.py               # Vimeo webhook handlers
│   │
│   ├── core/                         # Core application components
│   │   ├── settings.py               # Configuration (Pydantic BaseSettings)
│   │   ├── security.py               # Security utilities (JWT, sanitization)
│   │   ├── supabase_client.py        # Supabase database client
│   │   └── validation.py             # Pydantic request/response models
│   │
│   ├── middleware/                   # FastAPI middleware
│   │   └── rate_limiter.py           # Rate limiting middleware
│   │
│   ├── modules/                      # Business logic modules
│   │   ├── chat_history_manager.py   # Chat storage & retrieval
│   │   ├── embedding_manager.py      # OpenAI embeddings instance
│   │   ├── metadata_manager.py       # Video metadata caching
│   │   ├── pdf_processor.py          # PDF text extraction
│   │   ├── pdf_store.py              # PDF embedding storage
│   │   ├── retriever_chain.py        # LangChain conversation chain
│   │   ├── text_processor.py         # Text chunking & processing
│   │   ├── transcript_manager.py     # Caption/transcript handling
│   │   ├── utils.py                  # Utilities (logging, memory)
│   │   ├── vector_store.py           # Supabase vector operations (unified)
│   │   ├── vector_store_direct.py    # Direct vector operations
│   │   ├── vimeo_loader.py           # Vimeo API integration
│   │   └── whisper_transcriber.py    # Audio transcription (Whisper)
│   │
│   └── main.py                       # FastAPI app entry point
│
├── frontend/                         # Frontend SPA
│   ├── index.html                    # Main HTML file
│   ├── app.js                        # JavaScript application
│   ├── style.css                     # CSS styling
│   └── logo.png                      # Application logo
│
├── scripts/                          # Utility scripts
│   └── auto_update_embeddings.py    # Auto-update embeddings script
│
├── docs/                             # Documentation
│   └── (documentation files)
│
├── migrations/                       # Database migrations
│   └── supabase_migrations_complete.sql  # Complete Supabase schema
│
├── data/                             # Local data storage
│   └── uploads/                      # User-uploaded files
│       └── pdfs/                     # PDF uploads
│
├── .github/                          # GitHub CI/CD
│   └── workflows/
│       └── deploy.yml                # Vercel deployment workflow
│
├── requirements.txt                  # Python dependencies
├── runtime.txt                       # Python version (3.12)
├── pyproject.toml                    # Python project configuration
├── vercel.json                       # Vercel deployment configuration
├── .vercelignore                     # Vercel deployment exclusions
├── .gitignore                        # Git ignore patterns
└── README.md                         # This file
```

---

## Application Workflows

### 1. Application Startup Flow

```
1. Python process starts
2. backend/main.py imported
   ├── backend/core/settings.py loaded
   │   ├── .env file loaded (or created with defaults)
   │   ├── Settings() instance created
   │   └── Validation runs (if VALIDATE_CONFIG=true)
   ├── FastAPI app created
   ├── Middleware registered
   │   ├── GZipMiddleware
   │   ├── CORSMiddleware
   │   ├── TrustedHostMiddleware (production only)
   │   ├── Security headers middleware
   │   └── Rate limiting middleware
   ├── Routers imported (lazy loading)
   │   ├── /chat routes
   │   ├── /ingest routes
   │   ├── /pdf routes
   │   └── /webhooks routes
   └── Event handlers registered
3. Uvicorn starts server
4. Startup event fires
   ├── Logs startup message
   ├── Parses CORS origins
   ├── Cleans memory
   └── Logs memory usage
5. Server ready on port 8000
```

**Critical Path:**
- Settings must load successfully (raises SystemExit on failure)
- Routers must import without errors
- Supabase client must initialize (validates config)

**Failure Points:**
- Missing `.env` file → Creates minimal fallback
- Invalid API keys → Validation may fail (dev mode allows empty)
- Database connection failure → Only fails on first use

---

### 2. Chat Query Flow

```
User Query (Frontend)
    │
    ▼
POST /chat/query
    │
    ├─► Request Validation (Pydantic)
    │   └─► ChatRequest model
    │
    ├─► Greeting Detection
    │   └─► If greeting → Return greeting response (skip RAG)
    │
    ├─► Follow-up Detection
    │   └─► If follow-up → Retrieve previous context from memory
    │
    ├─► Generate Query Embedding
    │   └─► OpenAI text-embedding-3-small (1536 dims)
    │
    ├─► Vector Similarity Search
    │   └─► Search video_embeddings + pdf_embeddings
    │       └─► Cosine similarity scores
    │
    ├─► Threshold Filtering
    │   ├─► High confidence (≥0.5): Use directly
    │   ├─► Low confidence (≥0.4): Use with caution
    │   └─► Minimum threshold (≥0.3): Fallback
    │
    ├─► Context Preparation
    │   └─► Merge and format relevant documents
    │
    ├─► Response Generation
    │   ├─► If no relevant docs → "Sorry, I don't have this information"
    │   ├─► If partial context → LLM expansion with formatting
    │   └─► If sufficient context → ConversationalRetrievalChain
    │
    ├─► Source Attribution
    │   └─► Extract video timestamps, PDF pages, relevance scores
    │
    ├─► Store Interaction
    │   ├─► chat_history table
    │   └─► user_queries table (optional)
    │
    └─► Return Response
        └─► ChatResponse with answer, sources, conversation_id
```

**Key Components:**
- **Embedding Model**: `text-embedding-3-small` (OpenAI)
- **LLM Model**: `gpt-3.5-turbo` (OpenAI, via LangChain)
- **Vector Search**: Cosine similarity in Supabase
- **Memory**: ConversationBufferMemory (LangChain)
- **Thresholds**: Dynamic (0.5 high, 0.4 low, 0.3 minimum)

---

### 3. Video Ingestion Flow

```
POST /ingest/video/{video_id}
    │
    ├─► Duplicate Check
    │   └─► If exists and !force_transcription → Return early
    │
    ├─► Fetch Video Metadata
    │   └─► Vimeo API: GET /videos/{video_id}
    │
    ├─► Extract Transcript
    │   ├─► Try: Vimeo captions API
    │   │   └─► Parse SRT format
    │   └─► Fallback: Whisper transcription
    │       ├─► Download audio (yt-dlp)
    │       └─► Transcribe (OpenAI Whisper API)
    │
    ├─► Text Chunking
    │   └─► make_chunks_with_metadata()
    │       ├─► Chunk size: 1000 chars (default)
    │       ├─► Overlap: 200 chars (default)
    │       └─► Metadata: video_id, video_title, timestamps
    │
    ├─► Generate Embeddings
    │   └─► OpenAI embeddings for each chunk
    │
    ├─► Store in Supabase
    │   └─► video_embeddings table
    │       ├─► Batch inserts (25 chunks per batch)
    │       └─► Memory cleanup after each batch
    │
    └─► Return Response
        └─► VideoIngestResponse (chunk_count, processing_time, method)
```

**Key Components:**
- **Vimeo API**: Metadata and caption retrieval
- **Whisper API**: Audio transcription fallback
- **yt-dlp**: Audio extraction from Vimeo
- **Chunking**: Character-based with overlap
- **Storage**: Direct Supabase inserts

---

### 4. PDF Ingestion Flow

```
POST /pdf/pdf (multipart/form-data)
    │
    ├─► File Validation
    │   ├─► File extension: .pdf
    │   ├─► File size: ≤50MB
    │   └─► PDF structure validation
    │
    ├─► Save Temporary File
    │   └─► temp_{pdf_id}.pdf
    │
    ├─► Duplicate Check
    │   └─► If exists and !force_reprocess → Return early
    │
    ├─► Extract Text
    │   ├─► Try: PyMuPDF (fitz)
    │   └─► Fallback: PyPDF2
    │
    ├─► Extract Metadata
    │   └─► Title, author, page count, file size
    │
    ├─► Text Chunking
    │   └─► split_text_by_chars()
    │       ├─► Chunk size: 1000 chars (default)
    │       ├─► Overlap: 200 chars (default)
    │       └─► Metadata: pdf_id, pdf_title, page_number
    │
    ├─► Generate Embeddings
    │   └─► OpenAI embeddings for each chunk
    │
    ├─► Store in Supabase
    │   └─► pdf_embeddings table
    │       └─► Batch inserts with memory cleanup
    │
    ├─► Cleanup
    │   └─► Delete temporary file
    │
    └─► Return Response
        └─► PDFIngestResponse (chunks_processed, embeddings_stored)
```

**Key Components:**
- **PDF Libraries**: PyMuPDF (primary), PyPDF2 (fallback)
- **Chunking**: Character-based with page tracking
- **Storage**: pdf_embeddings table (separate from videos)

---

### 5. Embedding Generation Flow

```
Text Chunk
    │
    ├─► Get Embeddings Instance (cached)
    │   └─► OpenAIEmbeddings(
    │       model="text-embedding-3-small",
    │       chunk_size=100,
    │       max_retries=3,
    │       request_timeout=30
    │   )
    │
    ├─► Generate Embedding
    │   └─► embeddings.embed_query(chunk_text)
    │       └─► Returns: list[float] (1536 dimensions)
    │
    └─► Store in Supabase
        └─► embedding column (vector(1536))
```

**Key Details:**
- **Model**: `text-embedding-3-small` (1536 dimensions)
- **Caching**: Embeddings instance cached with `@lru_cache`
- **Error Handling**: Retries (3x), timeout (30s)
- **Memory**: Batch processing to reduce memory usage

---

### 6. Vector Retrieval Flow

```
User Query Embedding (1536 dims)
    │
    ├─► Load Vector Store
    │   └─► SupabaseVectorStore instance
    │
    ├─► Query Both Tables
    │   ├─► pdf_embeddings table
    │   └─► video_embeddings table
    │
    ├─► Calculate Similarity
    │   └─► Cosine similarity for each embedding
    │       └─► score = dot(a, b) / (norm(a) * norm(b))
    │
    ├─► Sort by Score
    │   └─► Higher scores = more relevant
    │
    ├─► Apply Thresholds
    │   ├─► High confidence: score ≥ 0.5
    │   ├─► Low confidence: score ≥ 0.4
    │   └─► Minimum: score ≥ 0.3
    │
    └─► Return Top K
        └─► List[(Document, score)] sorted by relevance
```

**Key Details:**
- **Search Method**: Cosine similarity (1 - distance)
- **Unified Search**: Searches both video_embeddings and pdf_embeddings
- **Thresholds**: Dynamic filtering based on confidence
- **Fallback**: Uses best available match if no high-confidence results

---

### 7. Response Generation Flow

```
Relevant Documents + Query
    │
    ├─► Context Preparation
    │   └─► Merge documents with source attribution
    │
    ├─► Determine Generation Path
    │   ├─► No relevant docs → "Sorry, I don't have this information"
    │   ├─► Partial context (<300 chars) → LLM expansion
    │   └─► Sufficient context → ConversationalRetrievalChain
    │
    ├─► LLM Generation (if needed)
    │   ├─► ChatOpenAI (gpt-3.5-turbo)
    │   ├─► Temperature: 0.0 (deterministic)
    │   ├─► Max tokens: 1000
    │   └─► ConversationBufferMemory (context from history)
    │
    ├─► Format Response
    │   └─► Educational formatting (Explanation, Example, Key Points)
    │
    └─► Return Response
        └─► Answer + Sources + Metadata
```

**Key Details:**
- **LLM**: GPT-3.5-turbo via LangChain
- **Memory**: ConversationBufferMemory (max 2000 tokens)
- **Formatting**: Structured educational responses
- **Fallback**: Graceful degradation when no relevant content

---

## API Documentation

### Chat Endpoints

#### `POST /chat/query`

Process a chat query and return an AI-generated response.

**Request Body:**
```json
{
  "request": {
    "query": "What does this video teach about machine learning?",
    "user_id": "user_123",
    "conversation_id": "conv_456",
    "include_sources": true,
    "top_k": 5,
    "temperature": 0.0,
    "max_tokens": 1000
  }
}
```

**Response:**
```json
{
  "answer": "Based on the training videos, machine learning is...",
  "sources": [
    {
      "video_title": "Introduction to AI",
      "video_id": "123456",
      "timestamp_start": 0,
      "timestamp_end": 102,
      "chunk_id": "0",
      "relevance_score": 0.95,
      "source_type": "video"
    },
    {
      "pdf_title": "ML Fundamentals",
      "pdf_id": "pdf_789",
      "page_number": 5,
      "chunk_id": "chunk_12",
      "relevance_score": 0.87,
      "source_type": "pdf"
    }
  ],
  "conversation_id": "conv_456",
  "processing_time": 1.234,
  "timestamp": 1704067200.0
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request format
- `422 Unprocessable Entity`: Validation error
- `503 Service Unavailable`: Embeddings or vector store unavailable
- `500 Internal Server Error`: Unexpected error

---

#### `GET /chat/history/{user_id}`

Retrieve chat history for a user.

**Response:**
```json
{
  "history": [
    {
      "id": "chat_123",
      "user_message": "What is React?",
      "bot_response": "React is a JavaScript library...",
      "video_id": "123456",
      "created_at": "2025-01-27T10:00:00Z"
    }
  ]
}
```

---

#### `GET /chat/sessions/{user_id}`

Get all conversation sessions for a user.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "conv_456",
      "message_count": 5,
      "last_message_at": "2025-01-27T10:30:00Z"
    }
  ]
}
```

---

#### `DELETE /chat/session/{user_id}/{session_id}`

Delete a specific conversation session.

**Response:**
```json
{
  "message": "Session deleted successfully"
}
```

---

#### `POST /chat/clear-memory/{session_id}`

Clear conversation memory for a session (LangChain memory).

**Response:**
```json
{
  "message": "Memory cleared successfully"
}
```

---

#### `DELETE /chat/history/{user_id}`

Delete all chat history for a user.

**Response:**
```json
{
  "message": "All chat history deleted successfully"
}
```

---

### Video Ingestion Endpoints

#### `POST /ingest/video/{video_id}`

Ingest a Vimeo video and generate embeddings.

**Request Body:**
```json
{
  "force_transcription": false,
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

**Response:**
```json
{
  "video_id": "123456",
  "video_title": "Introduction to Machine Learning",
  "chunk_count": 45,
  "message": "Ingestion completed and embeddings uploaded to Supabase.",
  "processing_time": 12.345,
  "transcription_method": "captions"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid video ID or metadata fetch failed
- `404 Not Found`: No captions or transcription found
- `500 Internal Server Error`: Processing or storage failure

---

#### `GET /ingest/health`

Health check for ingestion service.

**Response:**
```json
{
  "status": "healthy",
  "service": "video-ingestion",
  "memory_status": "ok",
  "timestamp": 1704067200.0
}
```

---

### PDF Ingestion Endpoints

#### `POST /pdf/pdf`

Upload and process a PDF file.

**Request:** `multipart/form-data`
- `file`: PDF file (required)
- `force_reprocess`: boolean (optional, default: false)

**Response:**
```json
{
  "pdf_id": "pdf_789",
  "filename": "document.pdf",
  "chunks_processed": 23,
  "embeddings_stored": 23,
  "processing_time": 5.678,
  "status": "success"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid file format or corrupted PDF
- `413 Request Entity Too Large`: File exceeds 50MB limit
- `500 Internal Server Error`: Processing or storage failure

---

#### `POST /pdf/batch`

Upload and process multiple PDF files.

**Request:** `multipart/form-data`
- `files`: Array of PDF files

**Response:**
```json
{
  "total_files": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "filename": "doc1.pdf",
      "status": "success",
      "chunks_processed": 15
    }
  ]
}
```

---

#### `GET /pdf/list`

List all processed PDF documents.

**Response:**
```json
{
  "pdfs": [
    {
      "pdf_id": "pdf_789",
      "pdf_title": "document.pdf",
      "chunk_count": 23,
      "created_at": "2025-01-27T10:00:00Z"
    }
  ]
}
```

---

#### `DELETE /pdf/{pdf_id}`

Delete a PDF and all its embeddings.

**Response:**
```json
{
  "message": "PDF deleted successfully",
  "embeddings_deleted": 23
}
```

---

#### `GET /pdf/{pdf_id}/status`

Get processing status for a PDF.

**Response:**
```json
{
  "pdf_id": "pdf_789",
  "status": "processed",
  "chunk_count": 23,
  "embeddings_count": 23
}
```

---

### Webhook Endpoints

#### `POST /webhooks/vimeo`

Handle Vimeo webhook events (video.ready, video.transcoded, video.uploaded).

**Request Body:**
```json
{
  "type": "video.ready",
  "clip": {
    "uri": "/videos/123456"
  }
}
```

**Response:**
```json
{
  "message": "Video processing started",
  "video_id": "123456"
}
```

**Processing:**
- Extracts video_id from payload
- Checks for duplicates
- Processes video asynchronously (background task)
- Returns immediately (non-blocking)

---

#### `GET /webhooks/health`

Health check for webhook service.

**Response:**
```json
{
  "status": "healthy",
  "service": "webhooks"
}
```

---

#### `POST /webhooks/test/{video_id}`

Test video processing (manual trigger).

**Response:**
```json
{
  "message": "Test processing started",
  "video_id": "123456"
}
```

---

### Utility Endpoints

#### `GET /health`

Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "dependencies": {
    "backend": "healthy"
  },
  "timestamp": "2025-01-27T10:00:00Z"
}
```

---

#### `GET /health/detailed`

Detailed health check with dependency validation.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "dependencies": {
    "backend": "healthy",
    "openai": "healthy",
    "supabase": "healthy",
    "vimeo": "healthy"
  },
  "timestamp": "2025-01-27T10:00:00Z"
}
```

---

#### `GET /`

Serve frontend SPA (index.html).

**Response:** HTML file or JSON fallback if frontend not found.

---

#### `GET /{file_path:path}`

Serve frontend static files (CSS, JS, images).

**Response:** Static file or index.html fallback (SPA routing).

---

#### `GET /docs`

API documentation (Swagger UI) - **Development only**

**Access:** Only available when `ENVIRONMENT=development`

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Supabase Configuration (REQUIRED)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-role-key-here

# Vimeo Configuration (REQUIRED)
VIMEO_ACCESS_TOKEN=your-vimeo-access-token-here
```

### Optional Environment Variables

```env
# Environment Configuration
ENVIRONMENT=development                    # development | staging | production
DEBUG=true                                 # Enable debug logging
VALIDATE_CONFIG=false                     # Validate config on startup

# AI Model Configuration
EMBEDDING_MODEL=text-embedding-3-small   # OpenAI embedding model
LLM_MODEL=gpt-3.5-turbo                   # OpenAI LLM model

# Security Configuration
SECRET_KEY=your-secret-key-change-in-production  # JWT secret key
ALGORITHM=HS256                           # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=30           # JWT expiration time

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000

# Text Processing Configuration
CHUNK_SIZE=1000                           # Text chunk size (characters)
CHUNK_OVERLAP=200                         # Chunk overlap (characters)
SUPABASE_TABLE=video_embeddings           # Default embeddings table

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60                  # Requests per minute per IP
```

### Environment Variable Validation

- **Development Mode**: Allows empty API keys (for testing)
- **Production Mode**: Requires all API keys to be set
- **Validation**: Checks format (e.g., OpenAI key starts with `sk-`)
- **Placeholder Detection**: Rejects placeholder values like "your-api-key-here"

---

## Local Development Setup

### Prerequisites

- **Python 3.12** (specified in `runtime.txt`)
- **FFmpeg** (for audio processing)
- **Supabase Account** (for database)
- **OpenAI API Key** (for embeddings and LLM)
- **Vimeo Access Token** (for video API)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd vimeo_video_chatbot
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `fastapi>=0.95.0` - Web framework
- `uvicorn>=0.20.0` - ASGI server
- `langchain==0.3.1` - RAG framework
- `langchain-openai==0.2.0` - OpenAI integration
- `openai==1.50.0` - OpenAI SDK
- `supabase==2.5.1` - Supabase client
- `pydub==0.25.1` - Audio processing
- `yt-dlp>=2024.12.13` - Video downloading
- `PyPDF2>=3.0.0` - PDF processing
- `PyMuPDF>=1.23.0` - PDF processing (optional, better performance)

### Step 4: Configure Environment

Create `.env` file in project root:

```bash
# Copy example (if exists)
copy config.example .env

# Or create manually
# Edit .env with your actual API keys (see Environment Configuration section)
```

### Step 5: Set Up Database

1. **Create Supabase Project**: https://supabase.com
2. **Enable pgvector Extension**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. **Run Migrations**: Execute `migrations/supabase_migrations_complete.sql` in Supabase SQL editor

**Tables Created:**
- `video_embeddings` - Video content embeddings
- `pdf_embeddings` - PDF content embeddings
- `chat_history` - Conversation history
- `user_queries` - Query tracking

**Functions Created:**
- `match_video_embeddings()` - Video similarity search
- `match_unified_embeddings()` - Unified search (videos + PDFs)

### Step 6: Install FFmpeg

**Windows:**
```bash
# Using chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Verify Installation:**
```bash
ffmpeg -version
```

### Step 7: Start the Server

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Access Points:**
- **Frontend**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs (development only)
- **Health Check**: http://127.0.0.1:8000/health

---

## Deployment

### Vercel Deployment

The project is configured for Vercel serverless deployment.

#### Configuration Files

**`vercel.json`:**
```json
{
  "version": 2,
  "builds": [
    { 
      "src": "backend/main.py", 
      "use": "@vercel/python",
      "config": {
        "includeFiles": ["frontend/**"]
      }
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "backend/main.py" }
  ]
}
```

**`runtime.txt`:**
```
3.12
```

**`.vercelignore`:**
- Excludes `venv/`, `data/`, `scripts/`, `docs/`, `migrations/`
- Excludes `.env` files (security)
- Excludes test artifacts and caches

#### Deployment Steps

1. **Connect Repository to Vercel**
2. **Set Environment Variables** in Vercel dashboard:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `VIMEO_ACCESS_TOKEN`
   - `ENVIRONMENT=production`
3. **Deploy**: Vercel automatically builds and deploys

#### Runtime Constraints

- **Bundle Size**: Must be <250MB (unzipped)
- **File System**: Read-only (except `/tmp`)
- **Memory**: Limited (optimizations in place)
- **Timeout**: 10s (Hobby), 60s (Pro)

#### Serverless-Safe Behavior

- **Logging**: Writes to stdout (Vercel-compatible)
- **Metadata**: Writes to `/tmp/backend_metadata` (if writable)
- **File Uploads**: Temporary files in current directory (cleaned up)
- **Static Files**: Served via FastAPI (included in bundle)

---

### Other Deployment Options

#### Docker Deployment

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Railway/Render

1. Connect GitHub repository
2. Set environment variables
3. Deploy (automatic detection of Python app)

---

## Logging & Debugging

### Logging Behavior

**Local Development:**
- Logs to stdout (console)
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Level: INFO (default)

**Vercel Deployment:**
- Logs to stdout (captured by Vercel)
- Available in Vercel dashboard
- No file logging (read-only filesystem)

**Log Locations:**
- Application logs: stdout
- Memory usage logs: `log_memory_usage()` calls
- Error logs: Exception handlers

### Common Error Scenarios

#### 1. OpenAI Authentication Error

**Symptoms:**
- `401 Incorrect API key provided`
- `Failed to generate embeddings`

**Debugging:**
```bash
# Check API key format
python -c "import os; key = os.getenv('OPENAI_API_KEY', ''); print('Key starts with sk-:', key.startswith('sk-'))"

# Test API connection
python -c "from openai import OpenAI; client = OpenAI(); print('API works:', client.models.list().data[0].id)"
```

**Solution:**
- Verify `OPENAI_API_KEY` in `.env`
- Ensure key starts with `sk-`
- Check key hasn't expired

---

#### 2. Supabase Connection Error

**Symptoms:**
- `Failed to create Supabase client`
- `Vector store unavailable`

**Debugging:**
```bash
# Test Supabase connection
python -c "from backend.core.supabase_client import test_connection; test_connection()"

# Check table exists
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.table('video_embeddings').select('id').limit(1).execute(); print('Table accessible:', len(result.data))"
```

**Solution:**
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
- Check Supabase project is active
- Verify pgvector extension is enabled

---

#### 3. Vector Search Not Working

**Symptoms:**
- No results returned
- Low similarity scores

**Debugging:**
```bash
# Check if embeddings exist
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.table('video_embeddings').select('*').limit(1).execute(); print('Embeddings exist:', len(result.data))"

# Verify pgvector extension
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.rpc('exec_sql', {'sql': \"SELECT * FROM pg_extension WHERE extname = 'vector'\"}).execute(); print('pgvector installed:', len(result.data))"
```

**Solution:**
- Ensure embeddings have been ingested
- Verify pgvector extension is installed
- Check similarity thresholds (may be too high)

---

#### 4. Memory Issues

**Symptoms:**
- `Memory usage high` warnings
- Slow performance
- Out of memory errors

**Debugging:**
```bash
# Check memory usage
python -c "from backend.modules.utils import get_memory_usage; print(f'Memory: {get_memory_usage():.2f} MB')"
```

**Solution:**
- Reduce batch sizes in ingestion
- Clear caches: `cleanup_memory()`
- Process fewer chunks at once

---

#### 5. CORS Errors

**Symptoms:**
- `CORS policy` errors in browser
- Frontend can't connect to backend

**Debugging:**
```bash
# Check CORS configuration
python -c "from backend.core.settings import settings; print('Allowed origins:', settings.ALLOWED_ORIGINS)"
```

**Solution:**
- Update `ALLOWED_ORIGINS` in `.env`
- Include frontend URL in allowed origins
- Restart server after changes

---

## Known Limitations

### Current Scalability Limits

1. **In-Memory Rate Limiting**
   - Uses in-memory dictionary (not distributed)
   - Resets on server restart
   - **Recommendation**: Use Redis for production

2. **Vector Search Performance**
   - Searches all embeddings (no pre-filtering)
   - No pagination for large result sets
   - **Recommendation**: Add filtering and pagination

3. **Memory Constraints**
   - Single-process server (no worker pool)
   - Limited by serverless memory limits
   - **Recommendation**: Optimize batch sizes

### Vector Store Limitations

1. **No Pre-filtering**
   - Searches entire table (no date/topic filters)
   - **Future**: Add metadata filtering

2. **Fixed Embedding Dimensions**
   - Hardcoded to 1536 (text-embedding-3-small)
   - **Future**: Support multiple models

3. **Threshold Tuning**
   - Static thresholds (0.5, 0.4, 0.3)
   - **Future**: Adaptive thresholds

### Memory Considerations

1. **Batch Processing**
   - Processes 25 chunks per batch (embeddings)
   - May be slow for large documents
   - **Future**: Configurable batch sizes

2. **Cache Management**
   - In-memory caches (not persistent)
   - **Future**: Redis-backed caching

3. **Conversation Memory**
   - Limited to 2000 tokens per session
   - **Future**: Configurable limits

---

## Troubleshooting

### Application Won't Start

**Check 1: Python Version**
```bash
python --version  # Should be 3.12
```

**Check 2: Dependencies**
```bash
pip list | grep -E "fastapi|langchain|openai|supabase"
```

**Check 3: Environment Variables**
```bash
python -c "from backend.core.settings import settings; print('Settings loaded:', settings.ENVIRONMENT)"
```

**Check 4: Import Errors**
```bash
python -c "from backend.main import app; print('App loaded successfully')"
```

---

### Chat Queries Return Empty Results

**Check 1: Embeddings Exist**
```bash
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.table('video_embeddings').select('id').limit(1).execute(); print('Embeddings:', len(result.data))"
```

**Check 2: Similarity Thresholds**
- Check logs for similarity scores
- Lower thresholds if needed (modify in `chat.py`)

**Check 3: Query Embedding Generation**
```bash
python -c "from backend.modules.embedding_manager import get_embeddings_instance; emb = get_embeddings_instance(); result = emb.embed_query('test'); print('Embedding dims:', len(result))"
```

---

### Video Ingestion Fails

**Check 1: Vimeo API Access**
```bash
python -c "from backend.modules.vimeo_loader import get_video_metadata; meta = get_video_metadata('123456'); print('Metadata:', meta.get('name'))"
```

**Check 2: FFmpeg Installation**
```bash
ffmpeg -version
```

**Check 3: Whisper API Access**
- Verify OpenAI API key has Whisper access
- Check API quota/limits

---

### PDF Ingestion Fails

**Check 1: PDF Library Installation**
```bash
python -c "import PyPDF2; import fitz; print('PDF libraries OK')"
```

**Check 2: File Size**
- Maximum: 50MB
- Check file size before upload

**Check 3: PDF Structure**
- Ensure PDF is not corrupted
- Try opening in PDF viewer

---

### Frontend Not Loading

**Check 1: Frontend Files Exist**
```bash
ls frontend/index.html frontend/app.js frontend/style.css
```

**Check 2: Server Running**
```bash
curl http://127.0.0.1:8000/health
```

**Check 3: CORS Configuration**
- Check browser console for CORS errors
- Verify `ALLOWED_ORIGINS` includes frontend URL

---

## Future Improvements

> **Note**: These are potential enhancements, not existing features.

### Immediate Enhancements
- [ ] **Background Task Processing** - Use Celery/Redis for async video processing
- [ ] **Caching Layer** - Redis for query results and embeddings
- [ ] **Comprehensive Testing** - Unit, integration, and E2E tests
- [ ] **API Rate Limiting** - Per-user rate limiting with Redis
- [ ] **WebSocket Support** - Real-time chat with streaming responses

### Advanced Features
- [ ] **Multi-language Support** - Internationalization for UI
- [ ] **Video Thumbnails** - Display video previews in responses
- [ ] **Advanced Search** - Filters by date, duration, topic
- [ ] **User Management** - Authentication and user profiles
- [ ] **Analytics Dashboard** - Usage statistics and insights

### Performance Optimizations
- [ ] **Embedding Caching** - Cache frequently used embeddings
- [ ] **Database Indexing** - Optimize query performance
- [ ] **CDN Integration** - Serve static assets via CDN
- [ ] **Load Balancing** - Multiple backend instances
- [ ] **Database Connection Pooling** - Optimize database connections

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) for the backend
- Uses [LangChain](https://langchain.com/) for RAG implementation
- Powered by [OpenAI](https://openai.com/) for embeddings and chat
- Database hosted on [Supabase](https://supabase.com/)
- Video processing with [Vimeo API](https://developer.vimeo.com/)

---

**Ready to chat with your Vimeo videos? Start the server and open http://127.0.0.1:8000!** 🚀
