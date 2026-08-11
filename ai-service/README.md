# Shared AI Service (OWL + HR Corner) — Phase 7

High-performance, modular, multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, **Qdrant Vector DB**, **fastembed**, **faster-whisper (STT)**, **FFmpeg**, **llama-server (Qwen2.5 0.5B GGUF)**, **Deterministic OWL Recommendation Engine**, and **Controlled Model Context Protocol (MCP) LMS Tools Integration**.

Designed to serve as the unified AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Phase 7)

```text
User Request
     │
     ▼
Laravel OWL / HR Corner
     │
     ▼
FastAPI AI Service Gateway
     │
     ├── Tool Registry (10 Read Tools)
     │    ├── get_user_learning_profile
     │    ├── get_learning_progress
     │    ├── get_user_assessments
     │    ├── search_learning_content
     │    ├── search_learning_playlist
     │    ├── get_content_detail
     │    ├── get_playlist_detail
     │    ├── get_learning_recommendations (Phase 6 Engine)
     │    ├── search_pdf_knowledge (Phase 4 Vector RAG)
     │    └── search_video_transcript (Phase 5 Vector RAG)
     │
     ▼
Qwen 0.5B GGUF Tool Calling Loop
     │
     ▼
LMS API / Vector Store Execution
     │
     ▼
Final User Answer Generation
```

---

## 🛠 Tech Stack (Phase 7)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
- **MCP Infrastructure**: Model Context Protocol (MCP) Tool Registry, Authorization Validator, and Execution Dispatcher
- **Recommendation Engine**: Deterministic multi-factor scoring (Division, Position, Learning Gap, Assessment Weakness, Category Relevance)
- **Audio Extraction**: FFmpeg (16kHz Mono WAV PCM)
- **Speech-to-Text**: `faster-whisper` (CTranslate2 INT8 CPU Execution)
- **Vector Database**: Qdrant Vector DB
- **Embeddings**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions)
- **PDF Extraction**: `pypdf`
- **Inference Server**: `llama-server` (llama.cpp)
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (`Q4_K_M` quantization)
- **Validation**: Pydantic v2 & Pydantic-Settings
- **HTTP Client**: HTTPX (Short connect timeout for high resilience)
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

# LMS API & MCP Configuration (Phase 7)
LMS_API_BASE_URL=http://owl-app.local
LMS_API_TOKEN=owl-lms-secret-token
LMS_API_TIMEOUT=10.0
MCP_ENABLED=true
MCP_MAX_TOOL_CALLS=5
TOOL_TIMEOUT=15.0

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

### MCP Tools Debug Endpoint
- **GET `/api/v1/tools`** — List registered MCP tools, schemas, and authorization requirements (Debug/Admin).

### Recommendation Engine
- **POST `/api/v1/recommendations`** — Generate personalized LMS recommendations with deterministic scoring & Qwen explanations.

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

### RAG & MCP Tool Chat Endpoint
- **POST `/api/v1/chat`** — Multi-tenant AI Chat completion with MCP Tool calling loop and PDF/Video citations.

---

## 🗺 Implementation Roadmap

```text
[x] PHASE 1 : FastAPI Foundation, Docker setup & Architecture Scaffolding
[x] PHASE 2 : llama-server + Qwen2.5 0.5B GGUF Integration
[x] PHASE 3 : Vector Database (Qdrant) Integration
[x] PHASE 4 : Document & PDF RAG Engine
[x] PHASE 5 : Video & Audio Transcription (Whisper)
[x] PHASE 6 : OWL Learning Recommendation Engine
[x] PHASE 7 : MCP / LMS Tools Integration (COMPLETED)
[ ] PHASE 8 : Conversational AI Agent (RAG + Recommendation + Tools)
```
