# Shared AI Service (OWL + HR Corner) — Phase 1

High-performance, modular, multi-tenant AI Backend Gateway built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, and **Docker**.

Designed to serve as the unified AI infrastructure layer for **OWL (Learning Management System)**, **HR Corner (Internal HR Application)**, and future enterprise applications.

---

## 🏗 System Architecture (Target Roadmap)

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
                    │      Qwen      │
                    │      RAG       │
                    │    Whisper     │
                    │ Recommendation │
                    │                │
                    └───────┬────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    Qdrant     │
                    │ Vector DB     │
                    └───────────────┘
                            ▲
                            │
                    ┌───────┴────────┐
                    │   HR Corner    │
                    │    REST API    │
                    └────────────────┘
```

---

## 🛠 Tech Stack (Phase 1)

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.110+
- **ASGI Server**: Uvicorn
- **Validation**: Pydantic v2 & Pydantic-Settings
- **HTTP Client**: HTTPX
- **Containerization**: Docker & Docker Compose
- **Testing**: Pytest & TestClient

---

## 📁 Directory Structure

```text
ai-service/
│
├── app/
│   ├── main.py                     # FastAPI entrypoint & middleware setup
│   │
│   ├── api/                        # Versioned API routes
│   │   └── v1/
│   │       ├── router.py           # Combined API v1 router
│   │       ├── health.py           # System & v1 health check
│   │       ├── chat.py             # Shared chat placeholder endpoint
│   │       ├── owl.py              # OWL application health endpoint
│   │       └── hr_corner.py        # HR Corner application health endpoint
│   │
│   ├── core/                       # Core configuration & utilities
│   │   ├── config.py               # Pydantic environment configuration
│   │   ├── logging.py              # Structured logging & duration middleware
│   │   └── security.py             # API Key security abstraction
│   │
│   ├── schemas/                    # Request & Response data models
│   │   ├── common.py               # Root & Health schemas
│   │   ├── chat.py                 # Multi-tenant chat payload schemas
│   │   └── application.py          # Application metadata & health schemas
│   │
│   ├── services/                   # Business logic abstraction layer
│   │   ├── llm_service.py          # LLM Provider abstraction (llama.cpp)
│   │   ├── owl_service.py          # OWL service abstraction
│   │   └── hr_corner_service.py    # HR Corner service abstraction
│   │
│   └── integrations/               # External HTTP Clients
│       ├── owl_client.py           # HTTP Client for OWL Laravel app
│       └── hr_corner_client.py     # HTTP Client for HR Corner app
│
├── tests/                          # Automated Pytest suite
│   ├── conftest.py
│   ├── test_root.py
│   ├── test_health.py
│   ├── test_owl.py
│   ├── test_hr_corner.py
│   └── test_chat.py
│
├── Dockerfile                      # Production slim Docker image
├── docker-compose.yml              # Container orchestration for Phase 1
├── requirements.txt                # Lightweight dependencies
├── .env.example                    # Environment settings template
├── .gitignore                      # Git exclusion rules
└── README.md                       # Project documentation
```

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `Shared AI Service` | Service identifier |
| `APP_ENV` | `development` | Environment mode |
| `APP_DEBUG` | `true` | Enables debug mode |
| `API_PREFIX` | `/api/v1` | API versioning prefix |
| `OWL_BASE_URL` | `http://owl-app.local` | OWL Laravel 9 base URL |
| `HR_CORNER_BASE_URL` | `http://hr-corner-app.local` | HR Corner API base URL |
| `LLM_PROVIDER` | `llama_cpp` | Target LLM engine provider |
| `LLM_BASE_URL` | `http://llama-server:8080` | llama-server API endpoint |
| `LOG_LEVEL` | `INFO` | Logger verbosity level |

---

## 🚀 Getting Started

### Option 1: Running Locally (Virtualenv)

1. Create and activate a Python 3.11+ virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. Open Swagger UI Documentation in your browser:
   `http://localhost:8000/docs`

---

### Option 2: Running with Docker Compose

1. Build and launch the container:
   ```bash
   docker compose build
   docker compose up -d
   ```

2. Check container status & health:
   ```bash
   docker compose ps
   ```

3. Inspect application logs:
   ```bash
   docker compose logs -f ai-service
   ```

---

## 🧪 Testing

Run the automated test suite with pytest:

```bash
pytest -v
```

---

## 📡 API Reference & Endpoints (Phase 1)

### System Endpoints
- **GET `/`** — Service root status
- **GET `/health`** — Basic health check for Docker healthcheck probe

### Business Endpoints (`/api/v1`)
- **GET `/api/v1/health`** — API v1 health status
- **GET `/api/v1/owl/health`** — OWL LMS health check placeholder
- **GET `/api/v1/hr-corner/health`** — HR Corner health check placeholder
- **POST `/api/v1/chat`** — Shared AI Chat entrypoint (Multi-tenant)

#### Chat Request Payload:
```json
{
  "application": "owl",
  "user_id": 123,
  "message": "Apa tujuan pembelajaran ini?"
}
```

#### Chat Response Payload:
```json
{
  "application": "owl",
  "message": "AI service is ready.",
  "provider": "llama_cpp",
  "model": null
}
```

---

## 🗺 Implementation Roadmap

```text
[x] PHASE 1 : FastAPI Foundation, Docker setup & Architecture Scaffolding (CURRENT)
[ ] PHASE 2 : llama-server + Qwen Integration
[ ] PHASE 3 : Vector Database (Qdrant) Integration
[ ] PHASE 4 : Document & PDF RAG Engine
[ ] PHASE 5 : Video & Audio Transcription (Whisper)
[ ] PHASE 6 : OWL LMS Integration Hooks
[ ] PHASE 7 : HR Corner API Hooks
[ ] PHASE 8 : Personalized Learning Recommendation Engine
[ ] PHASE 9 : MCP / Tool Calling Extensions
[ ] PHASE 10: Production Hardening, Rate Limiting & Monitoring
```
