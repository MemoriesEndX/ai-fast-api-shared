# Phase 20.8 — Cineku Removal & Public Chat Migration Report

> **Target System:** Multi-Tenant Shared AI Service (`ai-service`, `llama-server`, `qdrant`)  
> **Status:** COMPLETED & VERIFIED  
> **Branch Policy:** `main` (No branch switching)  
> **Total Test Suite:** 211 / 211 Passed (100%)  
> **Date:** August 2026  

---

## Executive Summary

In **Phase 20.8**, the Cineku tenant integration was completely decommissioned from the Shared AI Service and officially replaced with **Public Chat** (`application = "public-chat"`). 

Per strict project instructions:
1. **No Compatibility Layer**: A full, controlled replacement was performed (`cineku` $\to$ `public-chat`).
2. **Standardized Naming Convention**: The canonical identifier `application = "public-chat"` is enforced across schemas, security validators, routers, services, prompts, and UI components.
3. **Dedicated Endpoints**: Dedicated routes `POST /api/v1/public/chat` and `GET /api/v1/public/health` are operational with API key authentication (`PUBLIC_CHAT_AI_API_KEY`).
4. **Fuzzy Intent Router Scope**: **NOT** implemented in this phase (reserved strictly for the upcoming phase).
5. **Clean Codebase**: All active code and route definitions referring to Cineku were removed. Historical phase documentation remains intact as historical audit records.

---

## Architecture Transition: Before vs After

```
================================ BEFORE (Phase 16 - 20.7) ================================
Clients:           [OWL LMS]           [HR Corner]           [Cineku (Movies)]
Tenant ID:         "owl"               "hr-corner"           "cineku"
Endpoints:         /api/v1/owl/*       /api/v1/hr-corner/*   /api/v1/cineku/*
Service:           OwlService          HRCornerService       CinekuService
Environment:       OWL_AI_API_KEY      HR_AI_API_KEY         CINEKU_AI_API_KEY

================================ AFTER (Phase 20.8) =====================================
Clients:           [OWL LMS]           [HR Corner]           [Public Chat]
Tenant ID:         "owl"               "hr-corner"           "public-chat"
Endpoints:         /api/v1/owl/*       /api/v1/hr-corner/*   /api/v1/public/*
Service:           OwlService          HRCornerService       PublicChatService
Environment:       OWL_AI_API_KEY      HR_AI_API_KEY         PUBLIC_CHAT_AI_API_KEY
```

---

## Code Changes & Migration Details

### 1. Schema & Enums (`app/schemas/application.py`)
- Added `ApplicationEnum.PUBLIC_CHAT = "public-chat"`.
- Removed `ApplicationEnum.CINEKU`.
- Standardized canonical tenant validation to `owl`, `hr-corner`, `public-chat`.

### 2. Configuration (`app/core/config.py` & `.env.example`)
- Added `PUBLIC_CHAT_BASE_URL: str = "http://public-chat.local"`
- Added `PUBLIC_CHAT_AI_API_KEY: str = "public-chat-secret-api-key"` (dev default)
- Removed all `CINEKU_*` configuration variables.
- Updated `.env.example` with `YOUR_PUBLIC_CHAT_TENANT_SECRET_API_KEY_HERE`.

### 3. Security & Tenant Isolation (`app/core/security.py`)
- Updated `verify_api_key` to map `settings.PUBLIC_CHAT_AI_API_KEY` $\to$ `"public-chat"`.
- Enforced `validate_tenant_auth` rules:
  - `public-chat` API keys can only access `public-chat` tenant endpoints.
  - Cross-tenant access attempts between `public-chat`, `owl`, and `hr-corner` return `403 Forbidden` (`TENANT_ACCESS_DENIED`).

### 4. Service Layer (`app/services/public_chat_service.py`)
- Implemented `PublicChatService` with health check and business logic handling.
- Deleted obsolete `app/services/cineku_service.py`.

### 5. API Endpoints & Routing (`app/api/v1/public_chat.py` & `router.py`)
- Created `app/api/v1/public_chat.py` with:
  - `POST /api/v1/public/chat` — Dedicated Public Chat endpoint with rate limiting, input validation, and tenant authentication.
  - `GET /api/v1/public/health` — Dedicated Public Chat tenant health check.
- Mounted in `app/api/v1/router.py` under prefix `/public`.
- Deleted `app/api/v1/cineku.py`.

### 6. Orchestrator & Multi-Tenant Agent (`app/agent/orchestrator.py`)
- Updated tool isolation: Public Chat context is blocked from executing internal OWL / HR MCP tools.
- Configured dedicated system prompt for `public-chat`: General AI assistant with clean formatting, polite tone, and domain-agnostic capabilities.

### 7. Documentation & UI (`docs/chat.html`, `docs/pages/monitoring.html`, `docs/disaster-recovery.md`)
- Updated UI tenant selector dropdown to `Tenant: Public Chat` (`value="public-chat"`).
- Updated metrics documentation and disaster recovery architecture diagrams.

---

## Test Verification & Security Audit

### 1. Dedicated Public Chat Test Suite (`tests/test_public_chat.py`)
11 comprehensive test cases covering all Public Chat functionality:
- `test_public_chat_health`: 200 OK with `status: connected`.
- `test_public_chat_chat_valid`: 200 OK with `application: public-chat`.
- `test_public_chat_auth_missing_key`: 401 Unauthorized (`AUTHENTICATION_REQUIRED`).
- `test_public_chat_auth_invalid_key`: 401 Unauthorized (`AUTHENTICATION_REQUIRED`).
- `test_public_chat_accessing_owl_endpoint`: 403 Forbidden (`TENANT_ACCESS_DENIED`).
- `test_public_chat_accessing_hr_endpoint`: 403 Forbidden (`TENANT_ACCESS_DENIED`).
- `test_owl_accessing_public_chat_data`: 403 Forbidden (`TENANT_ACCESS_DENIED`).
- `test_public_chat_empty_message`: 400 Bad Request (`INVALID_REQUEST`).
- `test_public_chat_document_isolation`: Verified zero vector leakage.
- `test_public_chat_conversation_isolation`: Verified distinct session keying.
- `test_openapi_public_chat_endpoints`: Confirmed `/api/v1/public/*` exposed and `/api/v1/cineku/*` completely absent.

### 2. Full Regression Suite Results
```bash
./venv/bin/pytest
================ 211 passed, 425 warnings in 455.03s (0:07:35) =================
```
- **Total Test Cases**: 211
- **Passed**: 211 (100%)
- **Failed / Errors**: 0

---

## Scope Note: Fuzzy Intent Router

> [!NOTE]
> As specified in the Phase 20.8 instructions, the **Fuzzy Intent Router** was explicitly **NOT** implemented in this phase.
> The existing exact/regex/keyword intent router remains unchanged and stable.
> Fuzzy Intent Matching is queued for the upcoming phase.

---

## Conclusion & Readiness

The Cineku tenant has been cleanly decommissioned and replaced by **Public Chat** across the entire Shared AI Service codebase. All tests pass with zero regressions, and tenant isolation remains strictly enforced.
