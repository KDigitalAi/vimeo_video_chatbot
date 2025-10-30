# 🎥 Vimeo Video Chatbot

A modern, RAG-powered chatbot for querying Vimeo training videos using OpenAI embeddings and LangChain. Built with FastAPI backend and vanilla JavaScript frontend.

## Recent Deployment Fix Log (last 10 commits)

This section documents the recent sequence of fixes to get the app reliably deploying and running on Vercel (Python Serverless) with the SPA served by FastAPI.

1) e5dfae3b – connected frontend (2025-10-30)
- Purpose: Final wire-up after structuring the frontend folder. Verified SPA loads on Vercel domain.
- Outcome: Frontend working end-to-end with backend.

2) 27c6d01b – Frontend Added (2025-10-30)
- Purpose: Ensured required assets exist under `frontend/` so FastAPI can serve them in serverless context.
- Outcome: Static files present; mitigates “Frontend not found” fallback JSON response.

3) e75ad4bf – Restore frontend under `/frontend` (2025-10-30)
- Issue: FastAPI’s `root()` and static file handler look under `frontend/`; repo only had root-level `index.html`, `app.js`, `style.css`.
- Change: Recreated `frontend/index.html`, `frontend/app.js`, `frontend/style.css` (importing root CSS) and used a relative API base URL for production.
- Outcome: Backend could find and serve the SPA again.

4) 590fa1e2 – Bundle frontend assets with function (2025-10-30)
- Issue: Vercel did not include `frontend/**` in the serverless bundle, so static files were missing at runtime.
- Change: `vercel.json` build config → `includeFiles: ["frontend/**"]` for `@vercel/python` build.
- Outcome: `frontend/**` uploaded with the Python function; SPA available in production.

5) a9dab234 – Serverless-safe metadata storage (2025-10-30)
- Error: `OSError: [Errno 30] Read-only file system: 'backend/data'` during import of `metadata_manager.py`.
- Change: Write metadata to `/tmp/backend_metadata` (or `$METADATA_DIR`), wrap `mkdir` and writes with try/except; skip write rather than crash if not writable.
- Outcome: Import succeeds on Vercel’s read-only FS; ingest routes can load.

6) 5910d363 – Serverless-safe logging (2025-10-30)
- Error: `Read-only file system: 'backend/logs'` from `utils.get_logger()` trying to create files.
- Change: Prefer stdout logging; if available, write to `/tmp/backend_logs`; never create `backend/logs` on serverless.
- Outcome: App starts with logging to stdout; no FS errors.

7) a4bd5b36 – ci: remove `pyproject.toml` (2025-10-30)
- Reason: Allow Vercel’s Python builder to resolve from `requirements.txt` only, trimming serverless footprint and avoiding conflicting Python spec.
- Outcome: Cleaner dependency resolution for serverless build.

8) baeb7610 – Add `.vercelignore` (2025-10-30)
- Error: “Serverless Function exceeded unzipped maximum size of 250 MB”.
- Change: Ignore heavy directories and binaries: `venv/`, `.venv/`, `env/`, `uploads/`, `data/`, `models/`, `node_modules/`, `build/`, `dist/`, `tests/`, `docs/`, `.git/`, `.github/`, and large media/model files (`*.pdf`, `*.mp4`, `*.pt`, `*.bin`, `*.ckpt`, `*.onnx`, `*.h5`), plus caches.
- Outcome: Serverless bundle size reduced below 250MB.

9) 8a0294d7 – Modernize runtime & deps; simplify Vercel config (2025-10-30)
- Error: `spawn pip3.9 ENOENT` due to older runtime assumptions and strict pins.
- Changes:
  - `runtime.txt` → `3.12`.
  - `requirements.txt` → modern pins (`fastapi>=0.95.0`, `uvicorn>=0.20.0`, `werkzeug>=2.2.0`).
  - `vercel.json` → builds-only, pointing to `backend/main.py`.
  - `pyproject.toml` previously set to `>=3.11` (later removed in a4bd5b36 for lean builds).
- Outcome: Build uses modern Python and succeeds without pip3.9.

10) be85adee – vercel config file modified (2025-10-30)
- Initial iteration on Vercel configuration prior to the finalized builds-only approach.

### Key runtime behaviors after fixes
- FastAPI serves SPA from `frontend/` and APIs under `/` (e.g., `/chat/query`, `/health`).
- Logging writes to stdout (and `/tmp` when available) on Vercel.
- Any file writes default to `/tmp` to avoid read-only FS errors.
- `.vercelignore` keeps the serverless bundle well under the 250MB unzipped limit.

### How to verify (post-deploy)
- Open root URL → SPA loads (200), assets `/style.css?v=3`, `/app.js?v=3` 200.
- `GET /health` → 200 JSON.
- `POST /chat/query` → JSON response; if failing, clear cache and confirm same-origin API base in `frontend/index.html` meta tag is empty in production.

## Quick Start

```bash
# 1. Clone and setup
git clone <repository-url>
cd vimeo_video_chatbot

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy config.example .env
# Edit .env with your API keys

# 5. Run database migrations
python run_migration.py

# 6. Start the server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 7. Open in browser
# http://127.0.0.1:8000
```

## Architecture Overview

The Vimeo Video Chatbot is a full-stack RAG (Retrieval-Augmented Generation) application that processes Vimeo videos and enables natural language queries about their content.

### Components

- **Frontend**: Vanilla JavaScript SPA with modern ChatGPT-inspired UI
- **Backend**: FastAPI Python server with comprehensive API endpoints
- **Database**: Supabase PostgreSQL with pgvector extension for embeddings
- **AI/ML**: OpenAI GPT-3.5-turbo for chat, text-embedding-3-small for embeddings
- **Video Processing**: Vimeo API integration with Whisper transcription fallback

### Data Flow

```
Vimeo Videos → Audio Extraction → Transcription → Text Chunking → Embeddings → Supabase
                                                                    ↓
User Query → Embedding Search → Context Retrieval → LLM Generation → Response
```

## Project Structure

```
vimeo_video_chatbot/
├── backend/                          # FastAPI backend application
│   ├── api/                          # API route handlers
│   │   ├── chat.py                   # Chat query endpoints
│   │   ├── ingest.py                 # Video ingestion endpoints
│   │   └── webhooks.py               # Vimeo webhook handlers
│   ├── core/                         # Core application components
│   │   ├── settings.py               # Configuration management
│   │   ├── security.py               # Authentication & security
│   │   ├── supabase_client.py        # Database client
│   │   └── validation.py             # Pydantic models
│   ├── modules/                      # Business logic modules
│   │   ├── chat_history_manager.py   # Chat storage & retrieval
│   │   ├── embedding_manager.py      # OpenAI embeddings
│   │   ├── metadata_manager.py       # Video metadata handling
│   │   ├── retriever_chain.py        # LangChain conversation chain
│   │   ├── text_processor.py         # Text chunking & processing
│   │   ├── transcript_manager.py     # Caption/transcript handling
│   │   ├── utils.py                  # Utility functions
│   │   ├── vector_store.py           # Supabase vector operations
│   │   ├── vector_store_direct.py    # Direct vector operations
│   │   ├── vimeo_loader.py           # Vimeo API integration
│   │   └── whisper_transcriber.py    # Audio transcription
│   ├── data/                         # Data storage
│   │   └── metadata/                 # Video metadata cache
│   ├── logs/                         # Application logs
│   │   └── chatbot.log               # Main log file
│   └── main.py                       # FastAPI application entry point
├── frontend/                         # Frontend application
│   ├── index.html                    # Main HTML file
│   ├── app.js                        # JavaScript application
│   └── style.css                     # CSS styling
├── venv/                             # Python virtual environment
├── config.example                    # Environment configuration template
├── process_videos.py                 # Video processing script
├── run_migration.py                  # Database migration script
├── serve_frontend.py                 # Frontend development server
├── start_servers.bat                 # Windows startup script
├── start_servers.ps1                 # PowerShell startup script
├── test_env.py                       # Environment testing script
├── test_live_server.bat              # VS Code Live Server test
├── supabase_migrations.sql           # Database schema & functions
├── requirements.txt                  # Python dependencies
├── pyproject.toml                    # Python project configuration
├── package.json                      # Node.js dependencies (optional)
└── README.md                         # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8+ (tested with Python 3.12)
- Node.js 16+ (optional, for alternative frontend serving)
- FFmpeg (for audio processing)
- yt-dlp (installed via pip)

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# Copy the example configuration
copy config.example .env
```

Edit `.env` with your actual API keys:

```env
# Required API Keys
OPENAI_API_KEY=sk-your-openai-api-key-here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-key-here
VIMEO_ACCESS_TOKEN=your-vimeo-access-token-here

# Environment Configuration
ENVIRONMENT=development
DEBUG=true
VALIDATE_CONFIG=false

# CORS Configuration (for development)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5500,http://127.0.0.1:3000,http://127.0.0.1:5500

# AI Model Configuration
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-3.5-turbo

# Security Configuration
SECRET_KEY=development-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Text Processing Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SUPABASE_TABLE=video_embeddings

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

### 3. Database Setup

Run the database migrations to create tables and functions:

```bash
python run_migration.py
```

This creates:
- `video_embeddings` table with vector embeddings
- `chat_history` table for conversation storage
- `user_queries` table for query tracking
- `match_video_embeddings` and `match_documents` RPC functions

### 4. FFmpeg Installation

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

### 5. Running the Application

**Option 1: Full Stack (Recommended)**
```bash
# Start the FastAPI server (serves both API and frontend)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Access at: http://127.0.0.1:8000
```

**Option 2: Using Startup Scripts**
```bash
# Windows
start_servers.bat

# PowerShell
start_servers.ps1
```

**Option 3: Separate Frontend Server**
```bash
# Terminal 1: Backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
python serve_frontend.py
# Access at: http://127.0.0.1:3000
```

## Ingestion Pipeline

The video ingestion process converts Vimeo videos into searchable embeddings:

### Step-by-Step Process

1. **Video Discovery**
   ```python
   # Fetch videos from Vimeo account
   videos = get_user_videos(limit=10)
   ```

2. **Metadata Extraction**
   ```python
   # Get video metadata
   metadata = get_video_metadata(video_id)
   ```

3. **Transcript Generation**
   ```python
   # Try Vimeo captions first
   segments = get_transcript_segments_from_vimeo(video_id)
   
   # Fallback to Whisper transcription
   if not segments:
       segments = transcribe_vimeo_audio(video_id)
   ```

4. **Text Processing**
   ```python
   # Create chunks with metadata
   chunks = make_chunks_with_metadata(segments, video_id, video_title)
   ```

5. **Embedding Generation**
   ```python
   # Generate embeddings and store in Supabase
   stored_count = store_embeddings_directly(chunks)
   ```

### Running Ingestion

```bash
# Process all videos in your Vimeo account
python process_videos.py
```

## Chat Flow

The chat system enables natural language queries about video content:

### Step-by-Step Process

1. **User Query Reception**
   ```javascript
   // Frontend sends query to backend
   POST /chat/query
   {
     "query": "What does this video teach about GitHub?",
     "user_id": "user_123",
     "conversation_id": "conv_456",
     "include_sources": true,
     "top_k": 5
   }
   ```

2. **Query Processing**
   ```python
   # Generate embedding for user query
   query_embedding = embeddings.embed_query(request.query)
   ```

3. **Vector Search**
   ```python
   # Search similar content in video_embeddings
   docs = vector_store.similarity_search_by_vector_with_relevance_scores(
       query_embedding, k=request.top_k
   )
   ```

4. **LLM Generation**
   ```python
   # Generate response using LangChain
   result = chain.invoke({"question": request.query})
   answer = result.get("answer")
   ```

5. **Response & Storage**
   ```python
   # Store in chat_history and user_queries tables
   store_chat_interaction(user_id, session_id, query, answer, video_id)
   store_user_query(user_id, query, query_embedding, video_id)
   ```

## Database Schema

### Tables

**video_embeddings**
```sql
CREATE TABLE video_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    video_id TEXT,
    video_title TEXT,
    chunk_id TEXT,
    timestamp_start FLOAT,
    timestamp_end FLOAT,
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
    video_id TEXT,
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
    matched_video_id TEXT,
    matched_chunk_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### RPC Functions

**match_video_embeddings**
```sql
CREATE OR REPLACE FUNCTION match_video_embeddings(
    query_embedding vector(1536),
    match_count int DEFAULT 5
)
RETURNS SETOF video_embeddings
```

**match_documents** (LangChain compatible)
```sql
CREATE OR REPLACE FUNCTION match_documents(
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
```

## API Endpoints

### Chat Endpoints

**POST /chat/query**
```json
{
  "query": "What topics are covered in the training videos?",
  "user_id": "optional-user-id",
  "conversation_id": "optional-conversation-id",
  "include_sources": true,
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Based on the training videos, the topics covered include...",
  "sources": [
    {
      "video_title": "Introduction to AI",
      "video_id": "123456",
      "timestamp_start": 0,
      "timestamp_end": 102,
      "chunk_id": "0",
      "relevance_score": 0.95
    }
  ],
  "conversation_id": "conversation-id",
  "processing_time": 1.234,
  "tokens_used": null
}
```

### Ingestion Endpoints

**POST /ingest/video/{video_id}**
```json
{
  "force_transcription": false,
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

### Utility Endpoints

- `GET /health` - Health check
- `GET /` - Frontend interface
- `GET /docs` - API documentation (development only)

## Troubleshooting

### Common Issues

**1. CORS Errors**
```bash
# Check CORS configuration in .env
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Verify backend is running on correct port
curl http://127.0.0.1:8000/health
```

**2. Environment Variables Not Loading**
```bash
# Test environment loading
python test_env.py

# Verify .env file location (must be in project root)
ls -la .env
```

**3. FFmpeg Missing**
```bash
# Test FFmpeg installation
ffmpeg -version

# Install if missing (see FFmpeg Installation section)
```

**4. Supabase Function Missing**
```bash
# Run migrations
python run_migration.py

# Test function exists
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.rpc('match_video_embeddings', {'query_embedding': [0.0]*1536, 'match_count': 1}).execute(); print('Function works:', len(result.data))"
```

**5. OpenAI API Errors**
```bash
# Verify API key format
echo $OPENAI_API_KEY | head -c 10  # Should start with 'sk-'

# Test API connection
python -c "from openai import OpenAI; client = OpenAI(); print('API works:', client.models.list().data[0].id)"
```

**6. Vector Search Not Working**
```bash
# Check if embeddings exist
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.table('video_embeddings').select('*').limit(1).execute(); print('Embeddings exist:', len(result.data))"

# Verify pgvector extension
python -c "from backend.core.supabase_client import get_supabase; supabase = get_supabase(); result = supabase.rpc('exec_sql', {'sql': 'SELECT * FROM pg_extension WHERE extname = \\'vector\\''}).execute(); print('pgvector installed:', len(result.data))"
```

## Testing & Verification

### 1. Environment Verification
```bash
python test_env.py
```

### 2. Database Connection
```bash
python -c "from backend.core.supabase_client import test_connection; test_connection()"
```

### 3. End-to-End Chat Test
```bash
# Start server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Test greeting
curl -X POST "http://127.0.0.1:8000/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "hello", "user_id": "test_user"}'

# Test video query
curl -X POST "http://127.0.0.1:8000/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What does this video teach?", "user_id": "test_user", "include_sources": true}'
```

### 4. Video Ingestion Test
```bash
# Process a single video
python -c "
from backend.modules.vimeo_loader import get_user_videos
videos = get_user_videos(limit=1)
if videos:
    print('Videos found:', len(videos))
    print('First video:', videos[0].get('name'))
else:
    print('No videos found')
"
```

## Security & Deployment

### Environment Security

- **Never commit `.env` files** - Use `.env.example` as template
- **Rotate API keys regularly** - Especially in production
- **Use environment-specific configurations** - Different settings for dev/staging/prod
- **Enable HTTPS in production** - Use reverse proxy (nginx/Apache)

### Production Recommendations

1. **Update CORS settings:**
   ```env
   ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

2. **Enable authentication:**
   ```python
   # Uncomment in chat.py and ingest.py
   credentials: HTTPAuthorizationCredentials = Depends(security)
   ```

3. **Configure rate limiting:**
   ```python
   # Enable in chat.py
   if not check_rate_limit(request):
       raise HTTPException(status_code=429, detail="Rate limit exceeded")
   ```

4. **Use production secrets:**
   ```env
   SECRET_KEY=your-super-secure-secret-key-here
   ENVIRONMENT=production
   DEBUG=false
   ```

5. **Database security:**
   - Use Row Level Security (RLS) in Supabase
   - Limit service key permissions
   - Enable audit logging

### Deployment Options

**Docker Deployment:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Cloud Deployment:**
- **Railway/Render**: Direct Python deployment
- **Vercel**: Serverless functions
- **AWS/GCP**: Container deployment
- **Heroku**: Procfile deployment

## Next Steps & Improvements

### Immediate Enhancements
- [ ] **Background Task Processing** - Use Celery/Redis for video ingestion
- [ ] **Caching Layer** - Redis for query results and embeddings
- [ ] **Dependency Injection** - Cleaner architecture with DI container
- [ ] **Comprehensive Testing** - Unit, integration, and E2E tests
- [ ] **API Rate Limiting** - Per-user rate limiting with Redis
- [ ] **WebSocket Support** - Real-time chat with streaming responses

### Advanced Features
- [ ] **Multi-language Support** - Internationalization for UI
- [ ] **Video Thumbnails** - Display video previews in responses
- [ ] **Advanced Search** - Filters by date, duration, topic
- [ ] **User Management** - Authentication and user profiles
- [ ] **Analytics Dashboard** - Usage statistics and insights
- [ ] **Export Functionality** - Export conversations and data

### Performance Optimizations
- [ ] **Embedding Caching** - Cache frequently used embeddings
- [ ] **Database Indexing** - Optimize query performance
- [ ] **CDN Integration** - Serve static assets via CDN
- [ ] **Load Balancing** - Multiple backend instances
- [ ] **Database Connection Pooling** - Optimize database connections

### Monitoring & Observability
- [ ] **Structured Logging** - JSON logs with correlation IDs
- [ ] **Metrics Collection** - Prometheus/Grafana integration
- [ ] **Error Tracking** - Sentry integration
- [ ] **Health Checks** - Comprehensive health monitoring
- [ ] **Performance Monitoring** - APM integration

## Removed Duplicates

The following files were identified as duplicates or unnecessary and have been removed:

- **`index.html`** (root) - Redundant redirect page, backend serves frontend directly
- **`QUICK_START.md`** - Content merged into main README.md
- **`vimeo-chatbot.code-workspace`** - Personal VS Code workspace file, not needed in repository

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) for the backend
- Uses [LangChain](https://langchain.com/) for RAG implementation
- Powered by [OpenAI](https://openai.com/) for embeddings and chat
- Database hosted on [Supabase](https://supabase.com/)
- Video processing with [Vimeo API](https://developer.vimeo.com/)

---

**Ready to chat with your Vimeo videos? Start the server and open http://127.0.0.1:8000!** 🚀