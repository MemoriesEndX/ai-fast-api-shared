# Shared AI Service (OWL + HR Corner) — Phase 6

High-performance, modular, multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, **Qdrant Vector DB**, **fastembed**, **faster-whisper (STT)**, **FFmpeg**, **llama-server (Qwen2.5 0.5B GGUF)**, and **Deterministic OWL Recommendation Engine**.

Designed to serve as the unified AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Phase 6)

```text
               Laravel OWL LMS
                     │
                     │ User Profile & Candidates
                     ▼
           ┌──────────────────┐
           │   AI Service     │
           │  Recommendation  │
           └─────────┬────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Division     Position     Learning
                                History
        │            │            │
        └────────────┼────────────┘
                     ▼
             Candidate Filter
            & Exclusions
                     │
                     ▼
            Deterministic Scoring
             (30/25/20/15/10)
                     │
                     ▼
            Recommendation Ranking
                     │
                     ▼
            Qwen 0.5B GGUF
             (LLM Explanation)
                     │
                     ▼
               Laravel OWL
```

---

## 🛠 Tech Stack (Phase 6)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
- **Recommendation Engine**: Deterministic multi-factor scoring (Division, Position, Learning Gap, Assessment Weakness, Category Relevance)
- **Audio Extraction**: FFmpeg (16kHz Mono WAV PCM)
- **Speech-to-Text**: `faster-whisper` (CTranslate2 INT8 CPU Execution)
- **Vector Database**: Qdrant Vector DB
- **Embeddings**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions)
- **PDF Extraction**: `pypdf`
- **Inference Server**: `llama-server` (llama.cpp)
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (`Q4_K_M` quantization)
- **Validation**: Pydantic v2 & Pydantic-Settings
- **HTTP Client**: HTTPX
- **Containerization**: Docker & Docker Compose (Internal `ai-network` bridge)
- **Testing**: Pytest & TestClient

---

## ⚙️ Environment Configuration (`.env`)

```env
APP_NAME="Shared AI Service"
APP_ENV=development
APP_DEBUG=true
APP_VERSION=1.0.0

API_PREFIX=/api/v1

OWL_BASE_URL=http://owl-app.local
HR_CORNER_BASE_URL=http://hr-corner-app.local

LLM_PROVIDER=llama_cpp
LLM_BASE_URL=http://llama-server:8080
LLM_MODEL=qwen2.5-0.5b-instruct-q4_k_m.gguf
LLM_TIMEOUT=120
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.2

QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_PREFIX=shared_ai

EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RAG_TOP_K=3
RAG_SCORE_THRESHOLD=0.4

MAX_PDF_SIZE_MB=25
MAX_VIDEO_SIZE_MB=250
MAX_VIDEO_DURATION_SECONDS=3600
WHISPER_MODEL=tiny

# Recommendation Engine Weights
RECOMMENDATION_WEIGHT_DIVISION=30.0
RECOMMENDATION_WEIGHT_POSITION=25.0
RECOMMENDATION_WEIGHT_GAP=20.0
RECOMMENDATION_WEIGHT_ASSESSMENT=15.0
RECOMMENDATION_WEIGHT_RELEVANCE=10.0
RECOMMENDATION_DEFAULT_LIMIT=5
RECOMMENDATION_MAX_LIMIT=50

AI_API_KEY=dev-shared-ai-key-change-in-production
OWL_AI_API_KEY=owl-secret-api-key
HR_AI_API_KEY=hr-corner-secret-api-key

LOG_LEVEL=INFO
CORS_ORIGINS=["*"]
```

---

## 🚀 Docker Setup & Deployment

### Run Containers with Docker Compose:
```bash
docker compose build
docker compose up -d
```

### Container Status & Logs:
```bash
docker compose ps
docker compose logs -f ai-service
docker compose logs -f llama-server
docker compose logs -f qdrant
```

---

## 📡 API Reference & Endpoints

### Recommendation Engine
- **POST `/api/v1/recommendations`** — Generate personalized LMS recommendations with deterministic scoring & Qwen natural language explanations.

### Health Check Endpoints
- **GET `/health`** — Core system healthcheck
- **GET `/api/v1/health`** — API v1 healthcheck
- **GET `/api/v1/health/llm`** — LLM inference engine readiness check

### Video & Audio RAG Endpoints
- **POST `/api/v1/rag/videos/upload`** — Upload video file, extract audio using FFmpeg, transcribe using Whisper, and index into Qdrant.
- **GET `/api/v1/rag/videos/{document_id}/status?application=owl`** — Check transcription processing status.
- **POST `/api/v1/rag/videos/{document_id}/reindex`** — Re-process and re-index video document.

### Document RAG Endpoints
- **POST `/api/v1/rag/documents/upload`** — Upload and index PDF document.
- **POST `/api/v1/rag/documents/{document_id}/reindex`** — Re-index PDF document.
- **DELETE `/api/v1/rag/documents/{document_id}?application=owl`** — Delete PDF/Video document from vector store.
- **POST `/api/v1/rag/search`** — Search vector store across PDF and Video chunks.

### RAG Chat Endpoint
- **POST `/api/v1/chat`** — Multi-tenant AI Chat completion with PDF & Video timestamp sources.

---

## 🗺 Implementation Roadmap

```text
[x] PHASE 1 : FastAPI Foundation, Docker setup & Architecture Scaffolding
[x] PHASE 2 : llama-server + Qwen2.5 0.5B GGUF Integration
[x] PHASE 3 : Vector Database (Qdrant) Integration
[x] PHASE 4 : Document & PDF RAG Engine
[x] PHASE 5 : Video & Audio Transcription (Whisper)
[x] PHASE 6 : OWL Learning Recommendation Engine (COMPLETED)
[ ] PHASE 7 : MCP / LMS Tools Integration (NEXT)
```
