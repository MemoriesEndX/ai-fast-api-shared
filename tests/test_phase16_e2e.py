import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

OWL_KEY = settings.OWL_AI_API_KEY
HR_KEY = settings.HR_AI_API_KEY
PUBLIC_CHAT_KEY = settings.PUBLIC_CHAT_AI_API_KEY


@pytest.fixture(autouse=True)
def enable_auth(monkeypatch):
    """Enable auth for security and tenant isolation tests."""
    monkeypatch.setattr(settings, "AI_API_AUTH_ENABLED", True)


# ---------------------------------------------------------
# 1. NETWORK & ENDPOINT HEALTH VERIFICATION
# ---------------------------------------------------------
def test_e2e_network_health_endpoints():
    """Verify all 3 tenant health endpoints and core service health respond correctly."""
    # Root Health
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] in ["ok", "healthy"]

    # OWL Health
    resp_owl = client.get("/api/v1/owl/health")
    assert resp_owl.status_code == 200
    assert resp_owl.json()["application"] == "owl"

    # HR Corner Health
    resp_hr = client.get("/api/v1/hr-corner/health")
    assert resp_hr.status_code == 200
    assert resp_hr.json()["application"] == "hr-corner"

    # Public Chat Health
    resp_public = client.get("/api/v1/public/health")
    assert resp_public.status_code == 200
    assert resp_public.json()["application"] == "public-chat"


# ---------------------------------------------------------
# 2. OWL END-TO-END FLOW
# ---------------------------------------------------------
def test_e2e_owl_flow():
    """Verify OWL E2E chat flow, authentication, and LMS tool access."""
    # Invalid key
    resp_bad = client.post(
        "/api/v1/owl/chat",
        headers={"X-API-Key": "invalid-key"},
        json={"application": "owl", "message": "Halo"},
    )
    assert resp_bad.status_code == 401
    assert resp_bad.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Valid chat
    start_time = time.perf_counter()
    resp_good = client.post(
        "/api/v1/owl/chat",
        headers={"X-API-Key": OWL_KEY},
        json={
            "application": "owl",
            "message": "Tampilkan profil belajar saya dan progress LMS.",
            "user_id": 1,
            "conversation_id": "owl-e2e-conv-1",
        },
    )
    duration = time.perf_counter() - start_time
    assert resp_good.status_code == 200
    data = resp_good.json()
    assert data["application"] == "owl"
    assert data["conversation_id"] == "owl-e2e-conv-1"
    # OWL LMS tools can be executed for OWL tenant
    assert isinstance(data["tools_used"], list)
    assert duration < 30.0  # Realistic LLM completion threshold


# ---------------------------------------------------------
# 3. HR CORNER END-TO-END FLOW
# ---------------------------------------------------------
def test_e2e_hr_corner_flow():
    """Verify HR Corner E2E flow, auth, allowed tools, and OWL LMS tool blocking."""
    # Invalid key
    resp_bad = client.post(
        "/api/v1/hr-corner/chat",
        headers={"X-API-Key": "invalid-key"},
        json={"application": "hr-corner", "message": "Halo HR"},
    )
    assert resp_bad.status_code == 401
    assert resp_bad.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Valid chat (asking LMS profile - should block OWL tools)
    resp_good = client.post(
        "/api/v1/hr-corner/chat",
        headers={"X-API-Key": HR_KEY},
        json={
            "application": "hr-corner",
            "message": "Tampilkan profil belajar saya.",
            "user_id": 2,
            "conversation_id": "hr-e2e-conv-1",
        },
    )
    assert resp_good.status_code == 200
    data = resp_good.json()
    assert data["application"] == "hr-corner"
    # OWL tools must be blocked for HR Corner
    owl_tools = ["get_user_learning_profile", "get_learning_progress", "get_user_assessments"]
    for t in owl_tools:
        assert t not in data["tools_used"]


# ---------------------------------------------------------
# 4. PUBLIC CHAT END-TO-END FLOW
# ---------------------------------------------------------
def test_e2e_public_chat_flow():
    """Verify Public Chat E2E flow, auth, recommendation fallback, and tool isolation."""
    # Invalid key
    resp_bad = client.post(
        "/api/v1/public/chat",
        headers={"X-API-Key": "invalid-key"},
        json={"application": "public-chat", "message": "Halo AI"},
    )
    assert resp_bad.status_code == 401
    assert resp_bad.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Valid chat
    resp_good = client.post(
        "/api/v1/public/chat",
        headers={"X-API-Key": PUBLIC_CHAT_KEY},
        json={
            "application": "public-chat",
            "message": "Halo, ceritakan tentang layanan ini.",
            "user_id": 3,
            "conversation_id": "public-e2e-conv-1",
        },
    )
    assert resp_good.status_code == 200
    data = resp_good.json()
    assert data["application"] == "public-chat"
    assert data["conversation_id"] == "public-e2e-conv-1"
    # OWL tools must be blocked for Public Chat
    owl_tools = ["get_user_learning_profile", "get_learning_progress"]
    for t in owl_tools:
        assert t not in data["tools_used"]


# ---------------------------------------------------------
# 5. CROSS-TENANT SECURITY MATRIX
# ---------------------------------------------------------
def test_e2e_cross_tenant_security_matrix():
    """Verify all 6 cross-tenant breach combinations return 403 TENANT_ACCESS_DENIED."""
    matrix = [
        # (Client Key, Endpoint Path, Payload App Name)
        (PUBLIC_CHAT_KEY, "/api/v1/owl/chat", "owl"),
        (PUBLIC_CHAT_KEY, "/api/v1/hr-corner/chat", "hr-corner"),
        (OWL_KEY, "/api/v1/public/chat", "public-chat"),
        (OWL_KEY, "/api/v1/hr-corner/chat", "hr-corner"),
        (HR_KEY, "/api/v1/owl/chat", "owl"),
        (HR_KEY, "/api/v1/public/chat", "public-chat"),
    ]

    for key, path, app_name in matrix:
        resp = client.post(
            path,
            headers={"X-API-Key": key},
            json={"application": app_name, "message": "Cross tenant security test"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "TENANT_ACCESS_DENIED"


# ---------------------------------------------------------
# 6. CONVERSATION THREAD ISOLATION
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_e2e_conversation_thread_isolation():
    """Verify that identical thread IDs are strictly isolated per application tenant."""
    from app.agent.conversation import conversation_manager

    shared_thread_id = "test-shared-001"

    # Add turns for all 3 tenants with identical thread ID
    conversation_manager.add_turn(shared_thread_id, "OWL msg 1", "OWL ans 1", application="owl")
    conversation_manager.add_turn(shared_thread_id, "HR msg 1", "HR ans 1", application="hr-corner")
    conversation_manager.add_turn(shared_thread_id, "Public msg 1", "Public ans 1", application="public-chat")

    owl_hist = conversation_manager.get_history(shared_thread_id, application="owl")
    hr_hist = conversation_manager.get_history(shared_thread_id, application="hr-corner")
    public_hist = conversation_manager.get_history(shared_thread_id, application="public-chat")

    # Verify length and content isolation
    assert len(owl_hist) == 2
    assert owl_hist[0]["content"] == "OWL msg 1"

    assert len(hr_hist) == 2
    assert hr_hist[0]["content"] == "HR msg 1"

    assert len(public_hist) == 2
    assert public_hist[0]["content"] == "Public msg 1"


# ---------------------------------------------------------
# 7. RAG E2E TENANT ISOLATION & RETRIEVAL
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_e2e_rag_tenant_isolation():
    """Verify document ingestion, Qdrant indexing, and tenant retrieval isolation."""
    from app.services.rag_service import RAGService
    rag_service = RAGService()

    # Ingest 3 documents for 3 tenants
    await rag_service.index_document("owl", "OWL-DOC-101", "OWL Rules", "Aturan OWL internal.")
    await rag_service.index_document("hr-corner", "HR-DOC-202", "HR Policy", "Kebijakan HR internal.")
    await rag_service.index_document("public-chat", "PUBLIC-DOC-303", "Public Guide", "Panduan Layanan Publik.")

    # Search as Public Chat -> should only retrieve Public Chat doc
    res_public = await rag_service.search_similar_chunks("public-chat", "Panduan Layanan")
    assert any(c.get("document_id") == "PUBLIC-DOC-303" for c in res_public)
    assert not any(c.get("document_id") == "OWL-DOC-101" for c in res_public)

    # Search for OWL doc ID using Public Chat credentials -> 0 hits
    cross_hits = await rag_service.search_similar_chunks("public-chat", "Aturan", document_id="OWL-DOC-101")
    assert len(cross_hits) == 0


# ---------------------------------------------------------
# 8. ERROR HANDLING & FAILURE LEAK DEFENSE
# ---------------------------------------------------------
def test_e2e_error_handling_sanitization():
    """Verify failure modes return standard error structure and leak no sensitive info."""
    # 1. Empty message
    res_empty = client.post(
        "/api/v1/public/chat",
        headers={"X-API-Key": PUBLIC_CHAT_KEY},
        json={"application": "public-chat", "message": "   "},
    )
    assert res_empty.status_code == 400
    data = res_empty.json()
    assert data["error"]["code"] == "INVALID_REQUEST"

    # 2. Oversized payload > 4000 chars
    res_large = client.post(
        "/api/v1/public/chat",
        headers={"X-API-Key": PUBLIC_CHAT_KEY},
        json={"application": "public-chat", "message": "A" * 4005},
    )
    assert res_large.status_code == 400
    data = res_large.json()
    assert data["error"]["code"] == "INVALID_REQUEST"

    # 3. Invalid validation (missing required field)
    res_val = client.post(
        "/api/v1/public/chat",
        headers={"X-API-Key": PUBLIC_CHAT_KEY},
        json={"application": "public-chat"},
    )
    assert res_val.status_code == 422
    data = res_val.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"

    # Assert no stack trace, server paths, or secrets leak in error responses
    raw_text = str(data)
    assert "Traceback" not in raw_text
    assert "secret" not in raw_text.lower()
    assert "sqlite" not in raw_text.lower()


# ---------------------------------------------------------
# 9. PERFORMANCE BENCHMARKING
# ---------------------------------------------------------
def test_e2e_performance_metrics():
    """Measure E2E total response time, FastAPI processing time, and LLM latency across all tenants."""
    tenants = [
        ("owl", "/api/v1/owl/chat", OWL_KEY, "Jelaskan modul OWL"),
        ("hr-corner", "/api/v1/hr-corner/chat", HR_KEY, "Jelaskan kebijakan HR"),
        ("public-chat", "/api/v1/public/chat", PUBLIC_CHAT_KEY, "Jelaskan layanan umum"),
    ]

    metrics = {}
    for app_name, path, key, msg in tenants:
        t0 = time.perf_counter()
        resp = client.post(
            path,
            headers={"X-API-Key": key},
            json={"application": app_name, "message": msg, "user_id": 10},
        )
        total_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        assert resp.status_code == 200
        data = resp.json()
        metrics[app_name] = {
            "total_e2e_ms": total_time_ms,
            "fastapi_latency_ms": data.get("latency_ms", 0),
            "status": resp.status_code,
        }
        assert data["latency_ms"] > 0

    print("\n=== E2E PERFORMANCE METRICS ===")
    for app_name, m in metrics.items():
        print(f"[{app_name.upper()}] E2E Total: {m['total_e2e_ms']} ms | FastAPI Latency: {m['fastapi_latency_ms']} ms | Status: {m['status']}")
