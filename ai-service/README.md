# Shared AI Service (OWL + HR Corner) — Phase 2

High-performance, modular, multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, and **llama-server (Qwen2.5 0.5B GGUF)**.

Designed to serve as the unified AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Phase 2)

```text
                    ┌───────────────┐
                    │      OWL      │
                    │   Laravel 9   │
                    └───────┬───────┘
                            │
                            │ REST API
                            │
                    ┌───────▼────────┐
                    │                │
                    │   AI SERVICE   │
                    │                │
                    │    FastAPI     │
                    │  Prompt Layer  │
                    │  LLM Service   │
                    │                │
                    └───────┬────────┘
                            │
                            │ HTTP (OpenAI-compatible)
                            │ [Internal ai-network]
                            ▼
                    ┌───────────────┐
                    │ llama-server  │
                    │   llama.cpp   │
                    └───────┬───────┘
                            │
                            ▼
                    Qwen2.5 0.5B GGUF
                    (Q4_K_M Quant)
```

---

## 🛠 Tech Stack (Phase 2)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
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

AI_API_KEY=dev-shared-ai-key-change-in-production
OWL_AI_API_KEY=owl-secret-api-key
HR_AI_API_KEY=hr-corner-secret-api-key

LOG_LEVEL=INFO
CORS_ORIGINS=["*"]
```

---

## 🚀 Docker Setup & Deployment

### Download Model to Volumes:
Model GGUF file is persisted in `./models/qwen2.5-0.5b/` volume mount (not baked into the Docker image):

```bash
mkdir -p models/qwen2.5-0.5b
curl -L -o models/qwen2.5-0.5b/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
```

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
```

---

## 📡 API Reference & Endpoints

### Health Check Endpoints
- **GET `/health`** — Core system healthcheck
- **GET `/api/v1/health`** — API v1 healthcheck
- **GET `/api/v1/health/llm`** — LLM inference engine (`llama-server`) readiness check

### Application Health Endpoints
- **GET `/api/v1/owl/health`** — OWL LMS status
- **GET `/api/v1/hr-corner/health`** — HR Corner status

### Chat Endpoint
- **POST `/api/v1/chat`** — Multi-tenant AI Chat completion

#### Request Payload:
```json
{
  "application": "owl",
  "user_id": 123,
  "message": "Apa tujuan pembelajaran ini?"
}
```

#### Response Payload:
```json
{
  "application": "owl",
  "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
  "message": "Tujuan pembelajaran mencakup pemahaman konsep dasar, keterampilan praktis, dan evaluasi hasil belajar secara terstruktur.",
  "provider": "llama_cpp"
}
```

---

## 🧪 Testing with cURL

```bash
# System Health Check
curl -s http://localhost:8000/health | jq .

# LLM Backend Health Check
curl -s http://localhost:8000/api/v1/health/llm | jq .

# Chat completion for OWL
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-ai-key-change-in-production" \
  -d '{
    "application": "owl",
    "user_id": 123,
    "message": "Apa itu learning management system?"
  }' | jq .

# Chat completion for HR Corner
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-ai-key-change-in-production" \
  -d '{
    "application": "hr-corner",
    "user_id": 456,
    "message": "Apa fungsi utama HR Corner?"
  }' | jq .
```

---

## 🗺 Implementation Roadmap

```text
[x] PHASE 1 : FastAPI Foundation, Docker setup & Architecture Scaffolding
[x] PHASE 2 : llama-server + Qwen2.5 0.5B GGUF Integration (CURRENT)
[ ] PHASE 3 : Vector Database (Qdrant) Integration
[ ] PHASE 4 : Document & PDF RAG Engine
[ ] PHASE 5 : Video & Audio Transcription (Whisper)
[ ] PHASE 6 : OWL LMS Integration Hooks
[ ] PHASE 7 : HR Corner API Hooks
[ ] PHASE 8 : Personalized Learning Recommendation Engine
[ ] PHASE 9 : MCP / Tool Calling Extensions
[ ] PHASE 10: Production Hardening, Rate Limiting & Monitoring
```
