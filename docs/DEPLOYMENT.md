# Shared AI Service — Production Deployment Procedure

This guide outlines the step-by-step procedure for deploying the Shared AI Service stack (`ai-service`, `llama-server`, `qdrant`) to a production environment.

---

## 🏗 Target System Architecture

```text
Host Server
 └── Docker Engine (Compose v2)
      ├── shared-ai-service (FastAPI + Agent + MCP + RAG)
      ├── llama-server      (Qwen2.5 0.5B GGUF Model)
      └── qdrant            (Vector Database)
```

---

## 📋 Pre-deployment Requirements

1. **Hardware Minimum Specifications**:
   - **CPU**: 4 Cores (x86_64)
   - **RAM**: 8 GB RAM minimum
   - **Disk**: 20 GB SSD free space
2. **Software Prerequisites**:
   - Linux (Ubuntu 22.04 LTS recommended)
   - Docker Engine v24.0+
   - Docker Compose v2.20+
   - `curl` utility

---

## 🚀 Step-by-Step Deployment Instructions

### Step 1: Clone Repository
```bash
git clone <REPOSITORY_URL> /opt/ai-owl/ai-service
cd /opt/ai-owl/ai-service
```

### Step 2: Configure Environment Variables
Copy template and set production secrets:
```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and configure production tokens:
```env
APP_ENV=production
APP_DEBUG=false
AI_API_AUTH_ENABLED=true

# Security Tokens (MUST be generated via `openssl rand -hex 32`)
AI_API_KEY=<GENERATED_AI_SERVICE_KEY>
OWL_AI_API_KEY=<GENERATED_OWL_TENANT_KEY>
HR_AI_API_KEY=<GENERATED_HR_TENANT_KEY>

CORS_ORIGINS=["https://owl.example.com", "https://hr.example.com"]
```

### Step 3: Verify GGUF Model File Persistence
Ensure model file exists under `./models`:
```bash
mkdir -p models/qwen2.5-0.5b
# Download model if not present
curl -L -o models/qwen2.5-0.5b/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
```

### Step 4: Build Container Images
```bash
docker compose build --no-cache
```

### Step 5: Start Stack Containers
```bash
docker compose up -d
```

### Step 6: Verify Deployment Liveness & Readiness
```bash
# 1. Process Liveness Check
curl -s http://localhost:8000/health | jq .

# 2. Dependency Readiness Check
curl -s http://localhost:8000/ready | jq .
```

Expected readiness output:
```json
{
  "status": "ready",
  "qdrant": "ok",
  "llm_server": "ok"
}
```

---

## 💾 Qdrant Vector Data Backup & Restore Procedure

### Backup Procedure
To backup Qdrant persistent vector snapshot:
```bash
BACKUP_DIR="/var/backups/qdrant_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Snapshot Qdrant storage volume
docker run --rm \
  -v shared-ai-service_qdrant_data:/qdrant_storage \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/qdrant_vectors.tar.gz -C /qdrant_storage .

echo "Backup saved to: $BACKUP_DIR/qdrant_vectors.tar.gz"
```

### Restore Procedure
To restore vector storage from backup archive:
```bash
# 1. Stop services
docker compose down

# 2. Restore storage archive
docker run --rm \
  -v shared-ai-service_qdrant_data:/qdrant_storage \
  -v "$BACKUP_DIR":/backup \
  alpine sh -c "rm -rf /qdrant_storage/* && tar xzf /backup/qdrant_vectors.tar.gz -C /qdrant_storage"

# 3. Start services & verify
docker compose up -d
curl -s http://localhost:8000/ready | jq .
```

---

## 🧪 Production Smoke Test

Run complete API smoke test:
```bash
# Test Chat API with Authorization Bearer
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer <OWL_AI_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "application": "owl",
    "user_id": 123,
    "message": "Apa progress belajar saya saat ini?"
  }' | jq .
```
