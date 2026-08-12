# Shared AI Service — Disaster Recovery & Production Reliability Runbook

> **Document Version:** 1.0  
> **Target System:** Multi-Tenant Shared AI Service (OWL LMS, HR Corner, Cineku)  
> **Last Updated:** August 2026  

---

## 1. System Architecture Overview

The Multi-Tenant Shared AI Service runs as a containerized stack orchestrated via Docker / Podman Compose:

```text
                                Shared AI Service Gateway (Port 8000)
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
                OWL LMS                      HR Corner                       Cineku
             (owl-app.local)            (hr-corner-app.local)           (cineku-app.local)
                   │                             │                             │
                   └─────────────────────────────┼─────────────────────────────┘
                                                 │
                                         AI Service Engine
                                        /                 \
                          llama-server (Qwen)           Qdrant Vector DB
                             (Port 8080)                  (Port 6333)
                                 │                             │
                        GGUF Model Volume             qdrant_data Volume
```

### Components

1. **`ai-service`**: FastAPI Application Gateway providing LLM orchestration, Multi-tenant RAG Engine, recommendation pipeline, and MCP tools.
2. **`llama-server`**: High-performance `llama.cpp` inference server serving Qwen2.5-0.5B-Instruct GGUF model.
3. **`qdrant`**: Qdrant Vector Database storing embedding vectors, HNSW index, and payload metadata with tenant isolation.

---

## 2. Data Classification & Persistence Matrix

| Data Asset | Category | Storage Location | Retention / Persistence Strategy |
| :--- | :--- | :--- | :--- |
| **Qdrant Vectors & Collections** | **PERSISTENT** | `qdrant_data` Docker volume (`/qdrant/storage`) | Volume persisted across container restarts & rebuilds. Native snapshots taken daily. |
| **LLM Model Files** | **PERSISTENT** | `./models/qwen2.5-0.5b/` host directory | Mounted read-only (`:ro`) into `llama-server`. Shared across restarts. |
| **Application Configuration** | **PERSISTENT** | `.env` on host filesystem | Backed up securely in secret manager (Vault / K8s Secrets). |
| **Prometheus Metrics** | **EPHEMERAL** | In-memory `metrics_registry` | Metrics reset upon `ai-service` restart. Long-term metrics scraped by Prometheus. |
| **Temporary Upload Files** | **EPHEMERAL** | `/tmp` inside `ai-service` container | Deleted immediately after PDF page parsing or video Whisper transcription. |

---

## 3. Qdrant Backup & Snapshot Procedure

Qdrant provides native collection-level and storage-level snapshot capabilities without requiring service downtime.

### 3.1. Automatic / Programmatic Collection Snapshot

Call Qdrant Snapshot API to generate a collection snapshot:

```bash
# Create collection snapshot via curl
curl -X POST "http://localhost:6333/collections/shared_ai_documents/snapshots"
```

Or programmatically via `QdrantService` in Python:

```python
from app.services.qdrant_service import qdrant_service

# Take snapshot
result = await qdrant_service.create_snapshot()
# Returns: {"success": True, "snapshot_name": "shared_ai_documents_snap_1780000000.snapshot"}
```

### 3.2. Manual File-Level Backup of Volume

To perform a cold host-level volume backup:

```bash
# 1. Pause qdrant container or ensure write quiescence
docker compose pause qdrant

# 2. Archive qdrant volume directory
tar -czvf qdrant_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /var/lib/docker/volumes/ai-owl_qdrant_data/_data .

# 3. Resume qdrant container
docker compose unpause qdrant
```

---

## 4. Qdrant Restore Procedure

### 4.1. Restoring from Native Snapshot API

```bash
# Recover collection from snapshot file
curl -X POST "http://localhost:6333/collections/shared_ai_documents/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{
    "location": "http://localhost:6333/collections/shared_ai_documents/snapshots/shared_ai_documents_snap_1780000000.snapshot"
  }'
```

### 4.2. Programmatic Restore via `QdrantService`

```python
from app.services.qdrant_service import qdrant_service

# Restore from snapshot
success = await qdrant_service.restore_snapshot("shared_ai_documents_snap_1780000000.snapshot")
```

---

## 5. Recovery Procedures by Incident Type

### Incident A: AI Service Container Crash / Restart

```bash
# 1. Check container status
docker compose ps ai-service

# 2. Restart AI Service
docker compose restart ai-service

# 3. Verify Liveness and Readiness
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

### Incident B: Qwen / llama-server Failure

If `llama-server` crashes or becomes unresponsive:
1. `ai-service` `/ready` probe returns `503 Service Unavailable` with `dependencies: {"llm": "unavailable"}`.
2. `ai-service` does NOT crash-loop; it gracefully rejects chat requests with `AI_SERVICE_UNAVAILABLE`.
3. Restart `llama-server`:

```bash
docker compose restart llama-server
```

4. Once `llama-server` healthcheck passes (`curl http://localhost:8080/health`), `ai-service` automatically resumes processing requests.

### Incident C: Qdrant Database Failure

If Qdrant fails or is restarted:
1. `QdrantService` automatically switches to degraded in-memory mode if connection is lost.
2. Vector search calls return safe degraded responses without leaking internal stack traces.
3. Restart Qdrant container:

```bash
docker compose restart qdrant
```

4. `QdrantService` reconnects lazily on the next query.

### Incident D: Host Server Reboot / Full Stack Restart

```bash
# Bring up full stack in daemon mode
docker compose up -d

# Check startup ordering:
# 1. qdrant & llama-server start and pass healthchecks
# 2. shared-ai-service starts after dependencies are ready
docker compose ps
```

---

## 6. Document Hash Idempotency & Re-Indexing

To prevent duplicate vector entries during re-uploads or disaster recovery restores:
- Every ingested document or video chunk is hashed using **SHA-256 (`document_hash`)**.
- `qdrant_service.get_document_by_hash(application, document_hash)` verifies prior existence.
- Re-uploading an unchanged file returns the existing document metadata without creating redundant vector points.
- Updating a document via `/api/v1/rag/documents/{document_id}/reindex` purges old chunks before upserting new vectors.

---

## 7. Application Rollback Strategy

If a deployment contains a bug:
1. **Code Rollback**: Git checkout previous release tag (`git checkout v1.0.0`).
2. **Container Restart**: `docker compose up -d --build ai-service`.
3. **Data Compatibility**: Vector collection schema (`shared_ai_documents`) is decoupled from app release versions. Pre-existing embeddings remain 100% compatible.

---

## 8. Security Policy During Disaster Recovery

- **Secrets Handling**: Never commit `.env` or API keys (`AI_API_KEY`, `OWL_AI_API_KEY`, etc.) to source repositories. Restore configuration from `.env.example` using secret storage vault values.
- **Backup Sanitization**: Qdrant snapshot files contain raw payload chunk text and vectors. Snapshot files must be stored with `0600` file permissions and encrypted at rest.
- **Sanitized Logging**: All health, readiness, and exception handlers sanitize output to prevent accidental leakage of internal credentials or bearer tokens.
