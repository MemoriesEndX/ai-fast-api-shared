# Shared AI Service (OWL + HR Corner) — Phase 10

High-performance, hardened, production-ready, modular multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, **Qdrant Vector DB**, **fastembed**, **faster-whisper (STT)**, **FFmpeg**, **llama-server (Qwen2.5 0.5B GGUF)**, **Deterministic OWL Recommendation Engine**, **Controlled Model Context Protocol (MCP) LMS Tools Integration**, **Unified OWL LMS AI Agent**, and **Production Hardening Layer**.

Designed to serve as the unified, secure AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Phase 10 — Production Ready 3-Container Deployment)

```text
                 ┌───────────────────────────────────────┐
                 │          OWL / HR Corner              │
                 │          Future Applications          │
                 └──────────────────┬────────────────────┘
                                    │
                              HTTPS / REST API
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │            Shared AI Service                 │
             │                 FastAPI                      │
             ├──────────────────────────────────────────────┤
             │ Non-Root Container Execution (appuser:10001) │
             │ Bearer Token Auth & Security Verification    │
             │ Application & Tenant Authorization Isolation │
             │ Request ID Tracing (X-Request-ID Header)      │
             │ Token Bucket Rate Limiter & Circuit Breaker  │
             │ Standardized Error Response Formatter         │
             │ Global Centralized Exception Handlers        │
             │ Strict Pydantic Schema Input Validation      │
             │ Automatic Temporary File Cleanup (FFmpeg/WAV)│
             │ Path Traversal & Upload Security Sanitizer   │
             │ Liveness (/health) & Readiness (/ready)      │
             │ Log Rotation Limits (max-size=10m, max-files=3)│
             │ Unified AI Agent Orchestrator & Router       │
             └──────────────────────┬───────────────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
              Qdrant           Qwen 0.5B            MCP LMS
            Vector DB         llama-server           Tools
```

---

## 🛠 Tech Stack (Phase 10)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
- **Security & Hardening**: Non-root `appuser:10001` container, Bearer Token Auth, Tenant Isolation Guard, Path Traversal Sanitizer, File Upload Limits
- **Container Infrastructure**: Docker & Docker Compose (Strict 3-container topology: `ai-service`, `llama-server`, `qdrant`), Healthcheck dependency conditions (`condition: service_healthy`), Docker log rotation (`json-file`, `max-size: 10m`, `max-file: 3`), Resource CPU/Memory limits
- **Agent Orchestrator**: Intent Router, Loop Prevention (`CHAT_MAX_TOOL_CALLS=5`), Grounding Synthesizer, Conversation Thread Tracker
- **MCP Infrastructure**: Model Context Protocol (MCP) Tool Registry, Authorization Validator, and Execution Dispatcher (10 Registered Tools)
- **Recommendation Engine**: Multi-factor deterministic scoring (Division, Position, Learning Gap, Assessment Weakness, Category Relevance)
- **Audio Extraction**: FFmpeg (16kHz Mono WAV PCM via safe subprocess execution) with automatic `try...finally` temporary directory cleanup
- **Speech-to-Text**: `faster-whisper` (CTranslate2 INT8 CPU Execution)
- **Vector Database**: Qdrant Vector DB with persistent storage volumes & backup/restore runbooks
- **Embeddings**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions)
- **PDF Extraction**: `pypdf` (Idempotent page-aware text chunking)
- **Inference Server**: `llama-server` (llama.cpp)
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (`Q4_K_M` quantization)
- **Validation**: Pydantic v2 & Pydantic-Settings
- **Testing**: Pytest (92 Unit, Integration, Hardening & Evaluation Benchmark Tests)

---

## 📋 Public API Inventory

| Method | Path | Auth Required | Tenant Scope | Purpose | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | No | All | Service Root Identification | Active |
| `GET` | `/health` | No | All | Process Liveness Probe (Fast, zero heavy inference) | Active |
| `GET` | `/ready` | No | All | Dependency Readiness Probe (Checks Qdrant & llama-server) | Active |
| `POST` | `/api/v1/chat` | Bearer Token | `owl`, `hr-corner` | Unified AI Agent multi-tenant completion | Active |
| `POST` | `/api/v1/recommendations` | Bearer Token | `owl` | Deterministic learning recommendation ranking | Active |
| `GET` | `/api/v1/tools` | Bearer Token | All | List registered MCP tools & input schemas | Active |
| `POST` | `/api/v1/knowledge/documents` | Bearer Token | `owl`, `hr-corner` | Ingest Knowledge Document (PDF, Video, Audio) | Active |
| `POST` | `/api/v1/knowledge/search` | Bearer Token | `owl`, `hr-corner` | Direct Knowledge Vector Search | Active |
| `GET` | `/api/v1/knowledge/documents/{id}` | Bearer Token | `owl`, `hr-corner` | Get Knowledge Document Details & Status | Active |
| `GET` | `/api/v1/knowledge/documents` | Bearer Token | `owl`, `hr-corner` | List Knowledge Documents for Tenant | Active |
| `DELETE`| `/api/v1/knowledge/documents/{id}` | Bearer Token | `owl`, `hr-corner` | Delete Knowledge Document & Vectors | Active |
| `POST` | `/api/v1/knowledge/documents/{id}/reindex` | Bearer Token | `owl`, `hr-corner` | Atomic Reindex Knowledge Document | Active |
| `POST` | `/api/v1/rag/videos/upload` | Bearer Token | `owl`, `hr-corner` | Video ingestion (FFmpeg + Whisper + Qdrant) | Active |
| `GET` | `/api/v1/rag/videos/{doc_id}/status`| Bearer Token | `owl`, `hr-corner` | Video transcription status check | Active |
| `POST` | `/api/v1/rag/videos/{doc_id}/reindex`| Bearer Token | `owl`, `hr-corner` | Video document re-indexing | Active |
| `POST` | `/api/v1/rag/documents/upload` | Bearer Token | `owl`, `hr-corner` | PDF document upload and vector ingestion | Active |
| `POST` | `/api/v1/rag/documents/{doc_id}/reindex`| Bearer Token | `owl`, `hr-corner` | PDF document re-indexing | Active |
| `POST` | `/api/v1/rag/documents/index` | Bearer Token | `owl`, `hr-corner` | Text document direct vector indexing | Active |
| `DELETE`| `/api/v1/rag/documents/{doc_id}`| Bearer Token | `owl`, `hr-corner` | Delete document vector points from Qdrant | Active |
| `POST` | `/api/v1/rag/search` | Bearer Token | `owl`, `hr-corner` | Similarity search across vector chunks | Active |

---

## 📚 Knowledge Management & Ingestion API (Phase 11)

### 1. Ingest Knowledge Document (PDF, Video, Audio)
```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/documents" \
  -H "Authorization: Bearer owl-secret-api-key" \
  -F "file=@training_module.pdf" \
  -F "title=Training Module Laravel 2026" \
  -F "application=owl" \
  -F "document_id=pdf-mod-101" \
  -F "source_type=pdf"
```

### 2. Direct Knowledge Vector Search
```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/search" \
  -H "Authorization: Bearer owl-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "application": "owl",
    "query": "APD helm keselamatan",
    "source_type": "pdf",
    "top_k": 5
  }'
```

### 3. List Knowledge Documents for Tenant
```bash
curl -X GET "http://localhost:8000/api/v1/knowledge/documents?application=owl&page=1&page_size=20" \
  -H "Authorization: Bearer owl-secret-api-key"
```

### 4. Delete Knowledge Document & Vectors
```bash
curl -X DELETE "http://localhost:8000/api/v1/knowledge/documents/pdf-mod-101?application=owl" \
  -H "Authorization: Bearer owl-secret-api-key"
```

---

## 🔒 Production Hardening & Reliability Features

1. **Strict 3-Container Deployment**: Enforces `ai-service`, `llama-server`, `qdrant` without adding extra containers or heavy middleware.
2. **Non-Root Execution**: `Dockerfile` runs as unprivileged `appuser:10001` user and group.
3. **Log Rotation**: Docker Compose configures `json-file` log driver with `max-size: 10m` and `max-file: 3`.
4. **Temporary File Management**: Video and audio processing ensure `try...finally` deletion of temporary extraction directories (`/tmp/ai_*`).
5. **Healthcheck Dependencies**: `ai-service` startup depends on `llama-server` and `qdrant` reaching healthy states (`condition: service_healthy`).
6. **Production Runbooks**: Complete `DEPLOYMENT.md` and `ROLLBACK.md` guides provided for production deployment, data snapshotting, and disaster recovery.


---

## 📊 Benchmark & Test Suite Summary

- **Phase 1–8 Full Regression**: `74 / 74 PASSED`
- **Phase 8 50-Question Model Evaluation**: `50 / 50 PASSED (100% Accuracy)`
- **Phase 9 REST API Hardening Tests**: `10 / 10 PASSED`
- **Phase 10 Production Hardening Tests**: `8 / 8 PASSED`
- **Combined Pytest Suite**: **`92 PASSED / 0 FAILED (100% Pass Rate)`**

---

## 💻 Sample API Call (cURL)

```bash
curl -X POST \
  "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer owl-secret-api-key" \
  -H "X-Request-ID: trace-req-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "application": "owl",
    "user_id": 123,
    "message": "Pembelajaran apa yang cocok untuk posisi saya saat ini?"
  }'
```

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
[x] PHASE 8 : Unified OWL LMS AI Agent
[x] PHASE 9 : REST API Hardening & Shared API Contract
[x] PHASE 10 : Production Hardening & Deployment Reliability (COMPLETED)
```
