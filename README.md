# 📚 PDF Knowledge Chatbot

A production-ready, RAG-powered chatbot for querying PDF documents using OpenAI embeddings and LangChain. Built with FastAPI backend, optimized for serverless deployment on Vercel.

## 🎯 Project Overview

The **PDF Knowledge Chatbot** is a Retrieval-Augmented Generation (RAG) application that enables natural language queries over PDF document collections. Users can upload PDF documents, which are automatically processed, chunked, and embedded into a vector database. The chatbot then uses semantic search to retrieve relevant content and generates contextual responses using OpenAI's GPT models.

### High-Level Use Cases

- **Document Q&A**: Ask questions about uploaded PDF documents
- **Knowledge Base Search**: Search across multiple PDF documents simultaneously
- **Conversational Interface**: Maintain conversation context across multiple queries
- **Batch Processing**: Upload and process multiple PDFs at once
- **API Integration**: RESTful API for programmatic access

---

## ✨ Key Features

### PDF Ingestion
- **Single Upload**: Upload individual PDF files via API
- **Batch Upload**: Process multiple PDFs in a single request
- **Duplicate Detection**: Automatically detects and skips already-processed PDFs using content hash
- **Force Reprocessing**: Option to reprocess existing PDFs
- **Metadata Extraction**: Preserves PDF title, page numbers, and chunk IDs

### Text Processing & Embeddings
- **Intelligent Chunking**: Splits PDFs into optimal-sized chunks (1000 chars, 200 overlap)
- **OpenAI Embeddings**: Uses `text-embedding-3-small` (1536 dimensions) for vector generation
- **Content Cleaning**: Normalizes whitespace and preserves structure
- **Memory Management**: Automatic memory cleanup for serverless environments

### Vector Search & RAG
- **Supabase + pgvector**: PostgreSQL with vector extension for similarity search
- **Cosine Similarity**: Efficient vector similarity search with IVFFlat indexing
- **Dynamic Thresholds**: Multi-tier relevance filtering (High: 0.5, Low: 0.4, Minimum: 0.2, Absolute: 0.15)
- **Context Expansion**: Automatically includes related chunks from same PDF
- **Relevance Scoring**: Returns results with similarity scores

### Conversational Chat
- **Context-Aware Responses**: Uses LangChain ConversationalRetrievalChain for memory
- **Session Management**: Tracks conversations by user and session ID
- **Source Attribution**: Returns source documents with page numbers and relevance scores
- **Chat History**: Stores and retrieves conversation history
- **Follow-up Detection**: Automatically detects and handles follow-up questions

### API Documentation
- **Swagger UI**: Interactive API documentation at `/docs` (development only)
- **OpenAPI Schema**: Standard OpenAPI 3.1 specification at `/openapi.json`
- **ReDoc**: Alternative documentation interface at `/redoc` (development only)
- **Auto-disabled in Production**: Swagger UI automatically disabled when `ENVIRONMENT=production`

---

## 🛠 Technology Stack

### Backend Framework
- **FastAPI** (0.121.1): Modern Python web framework with automatic API documentation
- **Uvicorn** (0.38.0): ASGI server for production deployment
- **Starlette** (0.49.3): Lightweight ASGI framework (FastAPI dependency)
- **Pydantic** (2.8.2): Data validation and settings management

### Database & Vector Search
- **Supabase PostgreSQL**: Managed PostgreSQL database
- **pgvector**: PostgreSQL extension for vector similarity search
- **PostgREST** (0.16.11): RESTful API for PostgreSQL (via Supabase client)

### AI/ML
- **OpenAI** (1.50.0): GPT-3.5-turbo for chat, text-embedding-3-small for embeddings
- **LangChain** (0.3.1): Framework for building LLM applications
- **LangChain OpenAI** (0.2.0): OpenAI integration for LangChain
- **LangChain Core** (0.3.63): Core LangChain functionality

### PDF Processing
- **PyPDF2** (3.0.1): PDF text extraction
- **PyMuPDF** (1.26.6): Advanced PDF processing and metadata extraction

### Utilities
- **python-dotenv** (1.0.1): Environment variable management
- **NumPy** (1.26.4): Numerical operations for embeddings and cosine similarity
- **python-multipart** (0.0.6): File upload handling

### Deployment
- **Vercel**: Serverless function deployment
- **Python 3.12**: Runtime environment

---

## 📁 Project Structure

```
vimeo_video_chatbot/
├── app/                              # FastAPI backend application
│   ├── __init__.py                   # Package initialization
│   ├── main.py                       # FastAPI app entry point, router registration, middleware
│   │
│   ├── api/                          # API route handlers
│   │   └── routes/
│   │       ├── chat.py               # Chat endpoints (POST /chat/query, history, sessions)
│   │       └── pdf_ingest.py          # PDF ingestion endpoints (upload, list, delete)
│   │
│   ├── config/                       # Configuration management
│   │   ├── settings.py               # Environment settings & validation (Pydantic)
│   │   └── security.py               # Security utilities (input sanitization, validation)
│   │
│   ├── core/                         # Core functionality
│   │   └── middleware.py             # Rate limiting & CORS middleware
│   │
│   ├── database/                     # Database layer
│   │   ├── supabase.py               # Supabase client initialization
│   │   └── migrations.sql            # Database schema (tables, indexes, functions)
│   │
│   ├── models/                       # Data models
│   │   └── schemas.py                # Pydantic request/response models
│   │
│   ├── services/                     # Business logic services
│   │   ├── chat_history_manager.py  # Chat storage & retrieval
│   │   ├── embedding_manager.py      # OpenAI embeddings wrapper (cached)
│   │   ├── pdf_ingestion.py          # PDF ingestion pipeline (shared service)
│   │   ├── pdf_processor.py          # PDF text extraction & processing
│   │   ├── pdf_store.py              # PDF embeddings storage operations
│   │   ├── retriever_chain.py        # LangChain conversation chain
│   │   ├── text_processor.py         # Text chunking utilities
│   │   ├── vector_store.py           # Supabase vector operations (similarity search)
│   │   └── vector_store_direct.py    # Direct vector operations (storage)
│   │
│   └── utils/                        # Utilities
│       └── logger.py                 # Logging utilities (serverless-safe)
│
├── api/                              # Vercel serverless entry point
│   └── index.py                      # Vercel function handler
│
├── scripts/                          # Utility scripts
│   └── auto_update_embeddings.py    # Background script for batch PDF processing
│
├── tests/                            # Test directory
│   ├── unit/                         # Unit tests
│   └── integration/                  # Integration tests
│
├── requirements.txt                  # Python dependencies
├── runtime.txt                       # Python version (3.12)
├── vercel.json                       # Vercel deployment configuration
├── test_chat.py                      # Simple test script for chat endpoint
└── README.md                         # This file
```

### Entry Points

- **`app/main.py`**: FastAPI application initialization, router registration, middleware setup
- **`api/index.py`**: Vercel serverless function entry point (imports `app.main.app`)

### Critical Files

- **`app/config/settings.py`**: Environment configuration and validation
- **`app/services/pdf_ingestion.py`**: Centralized PDF ingestion pipeline
- **`app/services/vector_store.py`**: Vector similarity search implementation
- **`app/api/routes/chat.py`**: Chat query logic with RAG workflow
- **`app/database/migrations.sql`**: Database schema and indexes

---

## 🏗 System Architecture & Workflow

### PDF Upload Flow

```
1. User uploads PDF via POST /pdf/upload
   ↓
2. File validation (PDF format, size < 50MB)
   ↓
3. Generate PDF ID from content hash (MD5, first 12 chars)
   ↓
4. Check for duplicates in Supabase pdf_embeddings table
   ↓
5. Extract text from PDF (PyPDF2/PyMuPDF fallback)
   ↓
6. Split text into chunks (1000 chars, 200 overlap)
   ↓
7. Generate embeddings for each chunk (OpenAI text-embedding-3-small)
   ↓
8. Store embeddings in Supabase pdf_embeddings table
   ↓
9. Return processing results (chunks processed, embeddings stored)
```

### Chat Query / RAG Workflow

```
1. User sends query via POST /chat/query
   ↓
2. Generate query embedding (OpenAI text-embedding-3-small)
   ↓
3. Vector similarity search in pdf_embeddings table
   - Fetches up to k*3 rows (max 1000)
   - Computes cosine similarity for each
   - Sorts by relevance score
   - Returns top-k results
   ↓
4. Threshold filtering (multi-tier):
   - High confidence (≥0.5): Use directly
   - Low confidence (0.4-0.49): Use if no high confidence
   - Minimum (0.2-0.39): Use best document if exists
   - Absolute minimum (≥0.15): Use best document even if below minimum
   ↓
5. PDF expansion: Include related chunks from same PDF
   ↓
6. Context merging: Clean and merge content from retrieved documents
   ↓
7. Decision logic:
   - If no documents: Return fallback message
   - If documents exist: Always call LLM (even if context is empty)
   ↓
8. Generate response:
   - Use LangChain ConversationalRetrievalChain for context-aware responses
   - Or use clarification response for low-confidence matches
   ↓
9. Store interaction in chat_history table
   ↓
10. Store query in user_queries table
   ↓
11. Return response with sources and metadata
```

### Text Chunking Strategy

- **Chunk Size**: 1000 characters (configurable via `CHUNK_SIZE` env var)
- **Chunk Overlap**: 200 characters (configurable via `CHUNK_OVERLAP` env var)
- **Metadata**: Preserves PDF title, page number, chunk ID
- **Purpose**: Optimizes retrieval by balancing context size and granularity

### Vector Storage

- **Table**: `pdf_embeddings` in Supabase PostgreSQL
- **Vector Dimension**: 1536 (OpenAI text-embedding-3-small)
- **Index**: IVFFlat index on embedding column for fast similarity search
- **Metadata**: PDF ID, title, page number, chunk ID, source type, folder

### Similarity Thresholds

The system uses a multi-tier threshold system to prevent false negatives:

- **HIGH_CONFIDENCE_THRESHOLD** (0.5): High-quality matches, used directly
- **LOW_CONFIDENCE_THRESHOLD** (0.4): Moderate matches, used if no high-confidence results
- **MINIMUM_THRESHOLD** (0.2): Lower threshold to catch more relevant matches
- **ABSOLUTE_MINIMUM** (0.15): Absolute minimum - best document is used even if below minimum

**Why these thresholds?**
- `text-embedding-3-small` can produce lower similarity scores for valid matches
- Domain-specific or technical content may have lower scores but still be relevant
- The system prioritizes document presence over strict similarity scores
- Empty context (from content filtering) does NOT mean no documents exist

---

## 📡 API Documentation

### Base URL

- **Local Development**: `http://127.0.0.1:8000`
- **Production**: Your Vercel deployment URL

### Interactive Documentation

- **Swagger UI**: `http://127.0.0.1:8000/docs` (development only)
- **ReDoc**: `http://127.0.0.1:8000/redoc` (development only)
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json` (development only)

**Note**: Swagger UI is automatically disabled in production (`ENVIRONMENT=production`) for security.

### Health Endpoints

**GET `/health`**
- Basic health check
- Returns: `{"status": "healthy", "timestamp": "..."}`

**GET `/health/detailed`**
- Detailed health check with service status
- Checks: OpenAI API, Supabase connection, service availability
- Returns: Detailed status for each service

**GET `/`**
- API discovery endpoint
- Returns: API name, version, description

### Chat Endpoints

**POST `/chat/query`**
- Main chat query endpoint
- **Request Body**:
  ```json
  {
    "request": {
      "query": "What is Python?",
      "user_id": "user123",
      "conversation_id": "conv456",
      "top_k": 5,
      "include_sources": true
    }
  }
  ```
- **Response**:
  ```json
  {
    "answer": "Python is a programming language...",
    "sources": [
      {
        "source_type": "pdf",
        "pdf_title": "Python Guide",
        "pdf_id": "pdf_abc123",
        "page_number": 1,
        "chunk_id": "0",
        "relevance_score": 0.85,
        "source_name": "Python Guide"
      }
    ],
    "conversation_id": "conv456",
    "processing_time": 1.234,
    "tokens_used": null
  }
  ```

**GET `/chat/history/{user_id}`**
- Retrieve chat history for a user
- **Query Parameters**: `session_id` (optional), `limit` (default: 50)
- Returns: List of chat interactions

**GET `/chat/sessions/{user_id}`**
- Get all chat sessions for a user
- Returns: List of unique sessions with metadata

**GET `/chat/session/{user_id}/{session_id}`**
- Get information about a specific session (info endpoint)

**DELETE `/chat/session/{user_id}/{session_id}`**
- Delete a specific chat session

**GET `/chat/clear-memory/{session_id}`**
- Get information about clearing conversation memory (info endpoint)

**POST `/chat/clear-memory/{session_id}`**
- Clear conversation memory for a session

**DELETE `/chat/history/{user_id}`**
- Clear all chat history for a user

### PDF Ingestion Endpoints

**POST `/pdf/upload`** (or **POST `/pdf/pdf`**)
- Upload and process a single PDF file
- **Form Data**:
  - `file`: PDF file (multipart/form-data, required)
  - `force_reprocess`: Boolean (optional, default: false)
- **Response**:
  ```json
  {
    "pdf_id": "pdf_abc123",
    "filename": "document.pdf",
    "chunks_processed": 42,
    "embeddings_stored": 42,
    "processing_time": 5.67,
    "status": "success"
  }
  ```

**POST `/pdf/upload/batch`**
- Upload and process multiple PDF files
- **Form Data**:
  - `files`: Array of PDF files (multipart/form-data, required)
  - `force_reprocess`: Boolean (optional, default: false)
- **Response**: Batch processing summary with individual results

**GET `/pdf/list`**
- List all processed PDF documents
- Returns: List of PDFs with metadata (ID, title, chunk count, created date)

**GET `/pdf/{pdf_id}/status`**
- Get processing status for a specific PDF
- Returns: PDF ID, chunk count, status

**GET `/pdf/{pdf_id}`**
- Get information about a specific PDF (info endpoint)

**DELETE `/pdf/{pdf_id}`**
- Delete a PDF and all its embeddings

### Debug Endpoints (Development Only)

**GET `/debug/services`**
- Diagnostic endpoint showing service import status
- Useful for troubleshooting serverless deployment issues

**GET `/debug/routers`**
- Shows router registration status
- Lists all registered routers and their status

---

## 🔐 Environment Variables

Create a `.env` file in the project root with the following variables:

### Required Variables

```env
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-key-here
```

### Optional Configuration

```env
# Environment Configuration
ENVIRONMENT=development                    # Options: development, staging, production
DEBUG=true                                 # Enable debug mode

# AI Model Configuration
EMBEDDING_MODEL=text-embedding-3-small    # OpenAI embedding model
LLM_MODEL=gpt-3.5-turbo                   # OpenAI LLM model

# Text Processing Configuration
CHUNK_SIZE=1000                           # Text chunk size in characters
CHUNK_OVERLAP=200                         # Chunk overlap in characters
SUPABASE_TABLE=pdf_embeddings            # Supabase table name

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Security Configuration
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Configuration Validation
VALIDATE_CONFIG=false                     # Set to true to validate config on startup
```

**Important Notes**:
- Never commit `.env` files to version control
- Use different API keys for development and production
- In production, set `ENVIRONMENT=production` to disable Swagger UI
- The `SUPABASE_SERVICE_KEY` should have full database access (service role key)
- OpenAI API key must start with `sk-`

---

## 🚀 Local Development Setup

### Prerequisites

- **Python 3.12+** (tested with Python 3.12)
- **Supabase Account**: For PostgreSQL database with pgvector extension
- **OpenAI API Key**: For embeddings and chat generation

### Step-by-Step Setup

#### 1. Clone Repository

```bash
git clone <repository-url>
cd vimeo_video_chatbot
```

#### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example (if available)
copy .env.example .env

# Or create manually
# Edit .env with your API keys (see Environment Variables section)
```

#### 5. Database Setup

Run the database migrations in your Supabase SQL editor:

1. Open Supabase Dashboard → SQL Editor
2. Copy contents of `app/database/migrations.sql`
3. Execute the SQL script

This creates:
- `pdf_embeddings` table with vector embeddings
- `chat_history` table for conversation storage
- `user_queries` table for query tracking
- Indexes for performance optimization
- RPC functions for vector search
- pgvector extension

#### 6. Start the Server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The `--reload` flag enables auto-reload on code changes (development only).

#### 7. Verify Installation

Open your browser:
- **API**: `http://127.0.0.1:8000`
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## 🧪 Testing Guide

### Using Swagger UI (Recommended)

1. **Start the server** (see Local Development Setup)
2. **Open Swagger UI**: Navigate to `http://127.0.0.1:8000/docs`
3. **Test endpoints interactively**:
   - Click on an endpoint to expand
   - Click "Try it out"
   - Fill in parameters
   - Click "Execute"
   - Review response

### Recommended Testing Order

#### 1. Health Check
```
GET /health
```
Expected: `{"status": "healthy", "timestamp": "..."}`

#### 2. Upload a PDF
```
POST /pdf/upload
```
- Use Swagger UI to upload a test PDF
- Expected: Success response with `pdf_id`, `chunks_processed`, `embeddings_stored`

#### 3. List PDFs
```
GET /pdf/list
```
Expected: List containing your uploaded PDF

#### 4. Chat Query
```
POST /chat/query
```
Request Body:
```json
{
  "request": {
    "query": "What topics are covered in the PDF?",
    "user_id": "test_user",
    "include_sources": true
  }
}
```
Expected: Response with answer and source documents

#### 5. Chat History
```
GET /chat/history/test_user
```
Expected: List of previous chat interactions

### Testing with cURL

**Health Check:**
```bash
curl http://127.0.0.1:8000/health
```

**Upload PDF:**
```bash
curl -X POST "http://127.0.0.1:8000/pdf/upload" \
  -F "file=@document.pdf" \
  -F "force_reprocess=false"
```

**Chat Query:**
```bash
curl -X POST "http://127.0.0.1:8000/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "query": "What is Python?",
      "user_id": "test_user",
      "include_sources": true
    }
  }'
```

### Testing with Python

Create a `test_chat.py` file:

```python
import requests
import json

def test_chat(query):
    url = "http://127.0.0.1:8000/chat/query"
    payload = {
        "request": {
            "query": query,
            "user_id": "test_user",
            "include_sources": True
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"Query: {query}")
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"Sources: {len(result.get('sources', []))} sources found")
        print(f"Processing time: {result.get('processing_time', 0)}s")
        print("-" * 50)
        
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test queries
test_chat("Hello")
test_chat("What is Python?")
test_chat("Explain variables")
```

Run it:
```bash
python test_chat.py
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Errors

**Symptoms**: `ModuleNotFoundError` or import failures

**Solutions**:
```bash
# Verify all dependencies installed
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.12+

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

#### 2. Database Connection Issues

**Symptoms**: `Failed to connect to Supabase` or `Vector store unavailable`

**Solutions**:
```bash
# Verify environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY

# Test Supabase connection
python -c "from app.database.supabase import get_supabase; supabase = get_supabase(); print('Connected:', supabase is not None)"

# Check if pgvector extension is installed
# Run in Supabase SQL Editor:
# SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### 3. OpenAI API Errors

**Symptoms**: `OpenAI API key is invalid` or `401 Unauthorized`

**Solutions**:
```bash
# Verify API key format
echo $OPENAI_API_KEY | head -c 10  # Should start with 'sk-'

# Test API connection
python -c "from openai import OpenAI; client = OpenAI(); print('API works:', client.models.list().data[0].id)"

# Check API key in .env file
# Ensure no extra spaces or quotes
```

#### 4. PDF Processing Errors

**Symptoms**: `Failed to process PDF` or `No text extracted`

**Solutions**:
```bash
# Verify PDF libraries installed
python -c "import PyPDF2; import fitz; print('PDF libraries OK')"

# Check file size (max 50MB)
ls -lh document.pdf

# Test PDF processing
python -c "from app.services.pdf_processor import process_pdf_file; result = process_pdf_file('test.pdf'); print('Processed:', result)"
```

#### 5. Vector Search Not Working

**Symptoms**: Always returns "Sorry, I don't have this information"

**Solutions**:
```bash
# Check if embeddings exist
python -c "from app.database.supabase import get_supabase; supabase = get_supabase(); result = supabase.table('pdf_embeddings').select('*').limit(1).execute(); print('Embeddings exist:', len(result.data))"

# Check similarity scores in logs (development mode)
# Look for: "Retrieved X documents. Score range: min=X, max=Y"

# Verify threshold settings
# Check logs for: "After threshold filtering: X relevant docs"
```

#### 6. Swagger UI Not Loading

**Symptoms**: 404 on `/docs` endpoint

**Solutions**:
- Verify `ENVIRONMENT=development` in `.env`
- Check that server is running on correct port
- Try accessing `/openapi.json` directly
- In production, Swagger UI is intentionally disabled

#### 7. False "No Information" Responses

**Symptoms**: PDFs are uploaded but queries return "Sorry, I don't have this information"

**Possible Causes**:
1. **Threshold too strict**: Similarity scores below 0.15
2. **No embeddings stored**: Check database for embeddings
3. **Content filtering**: All content filtered out during merging
4. **Vector store error**: Check logs for vector store errors

**Solutions**:
```bash
# Check logs for similarity scores
# Look for: "Retrieved X documents. Score range: min=X, max=Y"

# Verify embeddings exist
# Check Supabase dashboard: pdf_embeddings table

# Check threshold logic
# System uses: HIGH (0.5), LOW (0.4), MINIMUM (0.2), ABSOLUTE_MINIMUM (0.15)

# Enable development logging
# Set ENVIRONMENT=development in .env
```

### Debugging Tips

1. **Enable Development Logging**: Set `ENVIRONMENT=development` in `.env`
2. **Check Server Logs**: Look for similarity scores, filtering decisions, and errors
3. **Use Health Endpoints**: `/health/detailed` shows service status
4. **Test Vector Search Directly**: Use Supabase SQL editor to test similarity search
5. **Check Embedding Dimensions**: Ensure query and document embeddings are both 1536 dimensions

---

## 🚢 Production Deployment

### Vercel Deployment

The application is optimized for Vercel serverless functions:

1. **Connect Repository**: Link your GitHub repository to Vercel
2. **Configure Environment Variables**: Set all required variables in Vercel Dashboard
3. **Set Production Environment**: `ENVIRONMENT=production` (disables Swagger UI)
4. **Deploy**: Vercel automatically detects `vercel.json` and deploys

### Serverless Considerations

#### Cold Starts
- Imports are wrapped in try/except to prevent failures
- Settings are loaded lazily to reduce initialization time
- Vector store is cached globally to reduce connection overhead

#### Memory Limits
- PDF processing includes automatic memory cleanup
- Large PDFs are processed in chunks
- Memory usage is logged in development mode

#### Timeout Limits
- Batch processing is optimized for serverless timeouts
- Single PDF uploads should complete within timeout
- Chat queries are optimized for fast responses

### Environment Variables in Production

Set environment variables in Vercel Dashboard:
1. Go to Project Settings → Environment Variables
2. Add all required variables (see Environment Variables section)
3. Set `ENVIRONMENT=production` to disable Swagger UI
4. Use production API keys (different from development)

### Bundle Size Optimization

The `.vercelignore` file excludes:
- Virtual environments (`venv/`, `.venv/`)
- Test files (`tests/`)
- Large files (`*.pdf`, `*.mp4`)
- Development files (`.git/`, `.github/`)

This keeps the serverless bundle under 250MB.

### Scaling Notes

#### Database Performance
- **Indexes**: Already created on `pdf_embeddings` table for fast vector search
- **Connection Pooling**: Consider using Supabase connection pooling for high traffic
- **Query Optimization**: Vector search uses IVFFlat index for efficient similarity search

#### API Performance
- **Rate Limiting**: Configured via `RATE_LIMIT_PER_MINUTE` (default: 60)
- **Memory Management**: PDF processing includes automatic memory cleanup
- **Batch Processing**: Optimized for processing multiple PDFs efficiently

#### Monitoring
- **Health Endpoints**: Use `/health` and `/health/detailed` for monitoring
- **Logging**: All logs go to stdout (Vercel automatically captures)
- **Error Tracking**: Consider integrating Sentry or similar for production

### Security Recommendations

1. **API Keys**: Rotate API keys regularly
2. **CORS**: Configure `ALLOWED_ORIGINS` for production domains only
3. **Rate Limiting**: Adjust `RATE_LIMIT_PER_MINUTE` based on usage
4. **Database Security**: Use Row Level Security (RLS) in Supabase
5. **Input Validation**: All inputs are validated via Pydantic models
6. **Swagger UI**: Automatically disabled in production

---

## 📊 Database Schema

### Tables

**pdf_embeddings**
```sql
CREATE TABLE pdf_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    pdf_id TEXT NOT NULL,
    pdf_title TEXT,
    chunk_id TEXT,
    page_number INTEGER,
    folder TEXT,
    source_type TEXT DEFAULT 'pdf',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**chat_history**
```sql
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    session_id TEXT,
    user_message TEXT NOT NULL,
    bot_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**user_queries**
```sql
CREATE TABLE user_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    query_text TEXT NOT NULL,
    query_embedding vector(1536),
    matched_chunk_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indexes

- **Vector Index**: IVFFlat index on `pdf_embeddings.embedding` for fast similarity search
- **PDF ID Index**: Index on `pdf_embeddings.pdf_id` for quick PDF lookups
- **Source Type Index**: Index on `pdf_embeddings.source_type` for filtering
- **User Index**: Index on `chat_history.user_id` for fast history retrieval
- **Timestamp Index**: Index on `created_at` for chronological queries

### Functions

- **match_pdf_embeddings**: Vector similarity search function
- **get_pdf_documents**: List all PDF documents
- **delete_pdf_document**: Delete PDF and all embeddings

---

## 🔄 Background Processing

### Auto-Update Script

The `scripts/auto_update_embeddings.py` script can be used to batch process PDFs:

```bash
python scripts/auto_update_embeddings.py
```

**Features**:
- Scans `uploads/pdfs/` directory for new PDFs
- Automatically detects duplicates
- Processes PDFs and generates embeddings
- Logs progress to `scripts/auto_update.log`

**Usage**:
1. Place PDFs in `uploads/pdfs/` directory
2. Run the script
3. Check logs for processing status

---

## 📝 Logging and Debugging

### Development Logging

When `ENVIRONMENT=development`, the system logs:
- Similarity scores (min, max, avg)
- Number of documents retrieved
- Threshold filtering decisions
- Context length after merging
- Vector store operations
- Memory usage

### Log Locations

- **Local Development**: Console output (stdout)
- **Vercel Production**: Vercel Dashboard → Logs
- **Background Scripts**: `scripts/auto_update.log`

### Debugging Tips

1. **Check Similarity Scores**: Look for "Retrieved X documents. Score range: min=X, max=Y"
2. **Verify Threshold Filtering**: Check "After threshold filtering: X relevant docs"
3. **Monitor Memory**: Look for memory usage warnings
4. **Check Vector Store**: Verify "Fetched X PDF embedding rows from database"
5. **Review Error Logs**: Check for exceptions and tracebacks

---

## ⚠️ Limitations and Known Constraints

### Current Limitations

1. **PDF Size**: Maximum 50MB per PDF file
2. **Chunk Size**: Fixed at 1000 characters (configurable via env var)
3. **Vector Dimension**: Fixed at 1536 (text-embedding-3-small)
4. **Similarity Thresholds**: Hardcoded in code (can be adjusted)
5. **Memory**: Serverless memory limits apply
6. **Timeout**: Serverless timeout limits apply (Vercel: 60s for Pro, 10s for Hobby)

### Known Constraints

1. **PDF-only Mode**: System only supports PDF documents (video support removed)
2. **Single Embedding Model**: Only supports text-embedding-3-small
3. **Single LLM Model**: Only supports gpt-3.5-turbo
4. **No Authentication**: API endpoints are not protected (add authentication for production)
5. **No Rate Limiting**: Rate limiting middleware exists but may need tuning

### Future Improvements

- [ ] Support for multiple embedding models
- [ ] Support for multiple LLM models (GPT-4, Claude, etc.)
- [ ] Authentication and authorization
- [ ] Advanced rate limiting
- [ ] Streaming responses
- [ ] WebSocket support for real-time chat
- [ ] PDF OCR for scanned documents
- [ ] Multi-language support
- [ ] Advanced analytics and monitoring

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) for the backend
- Uses [LangChain](https://langchain.com/) for RAG implementation
- Powered by [OpenAI](https://openai.com/) for embeddings and chat
- Database hosted on [Supabase](https://supabase.com/)
- Vector search powered by [pgvector](https://github.com/pgvector/pgvector)

---

**Ready to chat with your PDF documents? Start the server and open http://127.0.0.1:8000/docs!** 🚀
