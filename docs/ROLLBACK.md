# Shared AI Service — Production Rollback Procedure

This document provides exact steps to safely roll back the Shared AI Service stack in case of an unsuccessful deployment or runtime failure.

---

## 🚨 Rollback Triggers

Initiate rollback immediately if any of the following occur post-deployment:
1. `/ready` endpoint returns HTTP 503 (`AI_SERVICE_UNAVAILABLE`).
2. High rate of HTTP 500 internal errors on `/api/v1/chat`.
3. Container restart crash-loops (`docker compose ps`).
4. Severe performance regression (latency > 5000 ms).

---

## 🔄 Step-by-Step Rollback Plan

### Step 1: Graceful Service Shutdown
Stop current running containers without destroying persistent volumes:
```bash
cd /opt/ai-owl/ai-service
docker compose stop
```

### Step 2: Roll Back Git Repository State
Revert code to previous known stable release or commit tag:
```bash
# Fetch latest repository tags
git fetch --tags

# Checkout previous stable commit or tag (e.g., v1.0.0-phase9)
git checkout PREVIOUS_STABLE_COMMIT_HASH
```

### Step 3: Roll Back Environment Configuration
If `.env` was modified during deployment, restore previous configuration backup:
```bash
cp .env.bak .env
```

### Step 4: Restore Qdrant Vector Data (If Data Corruption Occurred)
If vector data corruption occurred during deployment:
```bash
# Locate latest pre-deployment backup directory
LATEST_BACKUP=$(ls -td /var/backups/qdrant_* | head -n 1)

# Restore vector data volume
docker run --rm \
  -v shared-ai-service_qdrant_data:/qdrant_storage \
  -v "$LATEST_BACKUP":/backup \
  alpine sh -c "rm -rf /qdrant_storage/* && tar xzf /backup/qdrant_vectors.tar.gz -C /qdrant_storage"
```

### Step 5: Rebuild and Restart Stack
Rebuild images cleanly from rolled-back codebase and launch containers:
```bash
docker compose build --no-cache
docker compose up -d
```

### Step 6: Rollback Verification
Execute health checks and smoke test to verify system recovery:
```bash
# 1. Check container health
docker compose ps

# 2. Check process liveness
curl -f http://localhost:8000/health

# 3. Check dependency readiness
curl -f http://localhost:8000/ready

# 4. Run sample query
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer owl-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"application":"owl","user_id":123,"message":"Status system check"}'
```
