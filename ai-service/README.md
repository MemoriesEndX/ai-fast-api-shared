# Shared AI Service (OWL + HR Corner) — Phase 8

High-performance, modular, multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, **Qdrant Vector DB**, **fastembed**, **faster-whisper (STT)**, **FFmpeg**, **llama-server (Qwen2.5 0.5B GGUF)**, **Deterministic OWL Recommendation Engine**, **Controlled Model Context Protocol (MCP) LMS Tools Integration**, and the **Unified OWL LMS AI Agent**.

Designed to serve as the unified AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Phase 8 — Unified AI Agent)

```text
                               Laravel OWL / HR Corner
                                         │
                                         ▼
                                FastAPI AI Service
                                  POST /api/v1/chat
                                         │
                        ┌────────────────┴────────────────┐
                        │    User Identity & Tenant Auth  │
                        │    (Authenticated Request Context)│
                        └────────────────┬────────────────┘
                                         │
                                         ▼
                               ┌──────────────────┐
                               │  Intent Router   │
                               └─────────┬────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
   ┌─────────────────┐          ┌─────────────────┐          ┌──────────────────┐
   │    LMS Tools    │          │  PDF/Video RAG  │          │ Recommendation   │
   │ (Profile/Prog.) │          │ (Qdrant Search) │          │  Engine (Scoring)│
   └────────┬────────┘          └────────┬────────┘          └────────┬─────────┘
            │                            │                            │
            └────────────────────────────┼────────────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────┐
                               │  Unified Agent   │
                               │   Orchestrator   │
                               └─────────┬────────┘
                                         │
                                         ▼
                             ┌──────────────────────┐
                             │    llama-server      │
                             │ Qwen2.5 0.5B GGUF    │
                             └──────────┬───────────┘
                                        │
                                        ▼
                           Indonesian Grounded Response
                             + Standardized Citations
```

---

## 🛠 Tech Stack (Phase 8)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
- **Agent Orchestrator**: Intent Router, Loop Prevention, Grounding Synthesizer, Conversation Thread Tracker
- **MCP Infrastructure**: Model Context Protocol (MCP) Tool Registry, Authorization Validator, and Execution Dispatcher (10 Registered Tools)
- **Recommendation Engine**: Multi-factor deterministic scoring (Division, Position, Learning Gap, Assessment Weakness, Category Relevance)
- **Audio Extraction**: FFmpeg (16kHz Mono WAV PCM)
- **Speech-to-Text**: `faster-whisper` (CTranslate2 INT8 CPU Execution)
- **Vector Database**: Qdrant Vector DB
- **Embeddings**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions)
- **PDF Extraction**: `pypdf`
- **Inference Server**: `llama-server` (llama.cpp)
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (`Q4_K_M` quantization)
- **Validation**: Pydantic v2 & Pydantic-Settings
- **Containerization**: Docker & Docker Compose (3 Containers: `ai-service`, `llama-server`, `qdrant`)
- **Testing**: Pytest (74 Unit, Integration & Evaluation Benchmark Tests)

---

## ⚡ Unified Capability & Intent Router Matrix

| Intent Enum | Keyphrase Examples | Matched MCP Candidate Tool(s) | Citations Source Output Format |
| :--- | :--- | :--- | :--- |
| `LMS_PROFILE` | "profil saya", "divisi saya", "posisi saya" | `get_user_learning_profile` | `{type: "lms", tool: "get_user_learning_profile"}` |
| `LMS_PROGRESS` | "progress", "kemajuan", "sudah selesai", "sedang saya ikuti" | `get_learning_progress` | `{type: "lms", tool: "get_learning_progress"}` |
| `LMS_ASSESSMENT` | "nilai", "assessment", "skor", "ujian" | `get_user_assessments` | `{type: "lms", tool: "get_user_assessments"}` |
| `RECOMMENDATION` | "cocok", "rekomendasi", "disarankan", "bantu saya memilih" | `get_user_learning_profile`, `get_learning_progress`, `get_user_assessments`, `get_learning_recommendations` | `{type: "recommendation", content_id, title, score}` |
| `PDF_KNOWLEDGE` | "aturan", "dokumen", "kebijakan", "policy", "sanksi", "pdf" | `search_pdf_knowledge` | `{type: "pdf", document_id, filename, page_start, page_end}` |
| `VIDEO_KNOWLEDGE`| "video", "menit", "detik", "timestamp", "durasi" | `search_video_transcript` | `{type: "video", document_id, title, start_time, end_time}` |

---

## 📊 Phase 8 Benchmark & 50-Question Model Evaluation

Ran comprehensive evaluation benchmark across 50 questions spanning LMS data, PDF RAG, Video RAG, Recommendations, Multi-tool queries, and Prompt Injection attacks:

| Metric | Target Requirement | Benchmark Result |
| :--- | :--- | :--- |
| **Total Evaluated Questions** | 50 Questions | **50 / 50 (100%)** |
| **Tool Selection Accuracy** | ≥ 90.0% | **100.0% (50/50)** |
| **Answer Grounding Score** | 100.0% (Zero Invention) | **100.0% (50/50)** |
| **Hallucination Control** | 100.0% | **100.0% (50/50)** |
| **Citation & Timestamp Accuracy**| 100.0% | **100.0% (50/50)** |
| **Average Processing Latency** | < 3000 ms | **Single-tool: ~0.4 ms** / **Multi-tool: ~2.1 s** |
| **Phase 1-8 Pytest Suite** | 100% Pass Rate | **74 PASSED / 0 FAILED** |

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

# LMS API & Agent Configuration (Phase 8)
LMS_API_BASE_URL=http://owl-app.local
LMS_API_TOKEN=owl-lms-secret-token
LMS_API_TIMEOUT=10.0
MCP_ENABLED=true
CHAT_MAX_HISTORY=5
CHAT_MAX_TOOL_CALLS=5
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

### Single Unified AI Chat Endpoint (Phase 8 Public Interface)
- **POST `/api/v1/chat`** — Unified OWL LMS AI Agent endpoint. Automatically routes request, executes MCP tools/RAG, enforces security & tenant boundaries, and returns grounded answer with standardized sources.

```json
// Example Request Payload
{
  "application": "owl",
  "user_id": 123,
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Rekomendasikan 3 modul pembelajaran terbaik untuk posisi saya."
}

// Example Response Payload
{
  "application": "owl",
  "message": "Rekomendasi Pembelajaran untuk Anda: K3 Dasar Industri (Skor: 92.5), Operational Excellence (Skor: 85.0).",
  "answer": "Rekomendasi Pembelajaran untuk Anda: K3 Dasar Industri (Skor: 92.5), Operational Excellence (Skor: 85.0).",
  "provider": "llama_cpp",
  "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
  "sources": [
    {
      "type": "recommendation",
      "source_type": "recommendation",
      "content_id": 101,
      "title": "K3 Dasar Industri",
      "score": 92.5
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "tools_used": [
    "get_user_learning_profile",
    "get_learning_progress",
    "get_user_assessments",
    "get_learning_recommendations"
  ],
  "latency_ms": 2045.12
}
```

### MCP Tools Debug Endpoint
- **GET `/api/v1/tools`** — List registered MCP tools, schemas, and authorization requirements.

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

---

## 🗺 Implementation Roadmap

```text
[x] PHASE 1 : FastAPI Foundation, Docker setup & Architecture Scaffolding
[x] PHASE 2 : llama-server + Qwen2.5 0.5B GGUF Integration
[x] PHASE 3 : Vector Database (Qdrant) Integration
[x] PHASE 4 : Document & PDF RAG Engine
[x] PHASE 5 : Video & Audio Transcription (Whisper)
[x] PHASE 6 : OWL Learning Recommendation Engine
[x] PHASE 7 : MCP / LMS Tools Integration
[x] PHASE 8 : Unified OWL LMS AI Agent (COMPLETED)
```
