import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test API Keys matching app.core.security
MASTER_KEY = "dev-shared-ai-key-change-in-production"
OWL_KEY = "owl-secret-api-key"
HR_KEY = "hr-corner-secret-api-key"
CINEKU_KEY = "cineku-secret-api-key"


def test_api_inventory_and_versioning_routes():
    """Verify all v1 API endpoints exist and respond under /api/v1/ prefix."""
    paths = list(app.openapi()["paths"].keys())
    
    # Verify core v1 routes exist in OpenAPI inventory
    assert "/api/v1/health" in paths
    assert "/api/v1/chat" in paths
    assert "/api/v1/owl/chat" in paths
    assert "/api/v1/hr-corner/chat" in paths
    assert "/api/v1/cineku/chat" in paths
    assert "/api/v1/rag/documents/upload" in paths
    assert "/api/v1/knowledge/documents" in paths
    assert "/api/v1/recommendations" in paths
    assert "/api/v1/tools" in paths
    assert "/api/v1/metrics" in paths


def test_authentication_missing_api_key():
    """Verify request with missing API key returns 401 Unauthorized with standard error format."""
    response = client.post("/api/v1/chat", json={"application": "owl", "message": "Halo"})
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "request_id" in data["error"]


def test_authentication_invalid_api_key():
    """Verify request with invalid API key returns 401 Unauthorized."""
    response = client.post(
        "/api/v1/chat",
        headers={"X-API-Key": "invalid-bogus-key-12345"},
        json={"application": "owl", "message": "Halo"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_tenant_isolation_matrix():
    """Verify strict tenant isolation across all application cross-access attempts."""

    # 1. Cineku Key -> OWL Endpoint (Forbidden)
    res1 = client.post("/api/v1/owl/chat", headers={"X-API-Key": CINEKU_KEY}, json={"application": "owl", "message": "Test"})
    assert res1.status_code == 403
    assert res1.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 2. Cineku Key -> HR Corner Endpoint (Forbidden)
    res2 = client.post("/api/v1/hr-corner/chat", headers={"X-API-Key": CINEKU_KEY}, json={"application": "hr-corner", "message": "Test"})
    assert res2.status_code == 403
    assert res2.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 3. OWL Key -> Cineku Endpoint (Forbidden)
    res3 = client.post("/api/v1/cineku/chat", headers={"X-API-Key": OWL_KEY}, json={"application": "cineku", "message": "Test"})
    assert res3.status_code == 403
    assert res3.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 4. OWL Key -> HR Corner Endpoint (Forbidden)
    res4 = client.post("/api/v1/hr-corner/chat", headers={"X-API-Key": OWL_KEY}, json={"application": "hr-corner", "message": "Test"})
    assert res4.status_code == 403
    assert res4.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 5. HR Corner Key -> OWL Endpoint (Forbidden)
    res5 = client.post("/api/v1/owl/chat", headers={"X-API-Key": HR_KEY}, json={"application": "owl", "message": "Test"})
    assert res5.status_code == 403
    assert res5.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 6. HR Corner Key -> Cineku Endpoint (Forbidden)
    res6 = client.post("/api/v1/cineku/chat", headers={"X-API-Key": HR_KEY}, json={"application": "cineku", "message": "Test"})
    assert res6.status_code == 403
    assert res6.json()["error"]["code"] == "TENANT_ACCESS_DENIED"


def test_rate_limit_application_isolation_and_429():
    """Verify application-aware rate limiting triggers 429 with Retry-After header and standard payload."""
    import time
    from app.core.rate_limit import rate_limiter

    # Manually saturate rate limit bucket for 'owl' tenant
    token_id = OWL_KEY[-8:]
    bucket_key = f"owl:chat:{token_id}"
    now = time.time()
    rate_limiter._history[bucket_key] = [now] * 120

    # OWL request should trigger 429
    response_owl = client.post("/api/v1/owl/chat", headers={"X-API-Key": OWL_KEY}, json={"application": "owl", "message": "Halo"})
    assert response_owl.status_code == 429
    assert "Retry-After" in response_owl.headers
    data = response_owl.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "request_id" in data["error"]

    # Clear test bucket history
    rate_limiter._history.clear()


def test_oversized_payload_rejection():
    """Verify message payload > 4000 chars is rejected with 400 Bad Request."""
    large_message = "A" * 4001
    response = client.post(
        "/api/v1/owl/chat",
        headers={"X-API-Key": OWL_KEY},
        json={"application": "owl", "message": large_message}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_openapi_specification():
    """Verify OpenAPI json endpoint is valid and exports API Gateway metadata."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "openapi" in spec
    assert "info" in spec
    assert "API Gateway" in spec["info"]["title"]
    assert "paths" in spec
    assert "/api/v1/chat" in spec["paths"]


def test_backward_compatibility_owl_hr_cineku():
    """Verify OWL, HR Corner, and Cineku dedicated chat endpoints respond properly with 200 OK."""
    # OWL Chat
    res_owl = client.post("/api/v1/owl/chat", headers={"X-API-Key": OWL_KEY}, json={"application": "owl", "message": "Apa itu OWL LMS?"})
    assert res_owl.status_code == 200
    assert res_owl.json()["application"] == "owl"

    # HR Corner Chat
    res_hr = client.post("/api/v1/hr-corner/chat", headers={"X-API-Key": HR_KEY}, json={"application": "hr-corner", "message": "Apa fungsi HR Corner?"})
    assert res_hr.status_code == 200
    assert res_hr.json()["application"] == "hr-corner"

    # Cineku Chat
    res_cineku = client.post("/api/v1/cineku/chat", headers={"X-API-Key": CINEKU_KEY}, json={"application": "cineku", "message": "Rekomendasi film komedi terbaik."})
    assert res_cineku.status_code == 200
    assert res_cineku.json()["application"] == "cineku"


def test_security_response_headers():
    """Verify API Gateway response contains essential security headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "X-Request-ID" in response.headers
