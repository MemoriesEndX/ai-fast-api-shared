import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.logging import sanitize_log_data, resolve_tenant_from_request
from app.core.metrics import metrics_registry

client = TestClient(app)


def test_request_id_auto_generation():
    """Verify that X-Request-ID is generated if omitted by client."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    assert len(req_id) > 10


def test_request_id_propagation():
    """Verify that valid client-supplied X-Request-ID is preserved in response headers."""
    custom_req_id = "test-req-id-custom-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_req_id


def test_liveness_health_endpoint():
    """Verify /health endpoint returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-service"


def test_readiness_health_endpoint():
    """Verify /ready endpoint returns HTTP 200 ready response."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "dependencies" in data


def test_llm_health_check_endpoint():
    """Verify /api/v1/health/llm endpoint."""
    response = client.get("/api/v1/health/llm")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "provider" in data
    assert "model" in data


def test_qdrant_health_check():
    """Verify Qdrant service health check function."""
    import asyncio
    from app.services.qdrant_service import qdrant_service
    res = asyncio.run(qdrant_service.check_health())
    assert "status" in res
    assert res["service"] == "qdrant"


def test_metrics_prometheus_endpoint():
    """Verify /metrics returns Prometheus exposition format text."""
    # Trigger a request to record metrics
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "# HELP ai_requests_total" in body
    assert "# TYPE ai_requests_total" in body


def test_metrics_json_endpoint():
    """Verify /metrics/json returns snapshot JSON."""
    response = client.get("/metrics/json")
    assert response.status_code == 200
    data = response.json()
    assert "counters" in data
    assert "histograms" in data
    assert "timestamp" in data


def test_tenant_logging_resolution():
    """Verify resolve_tenant_from_request accurately extracts application ID."""
    from starlette.requests import Request
    from starlette.datastructures import Headers

    # Test via Header
    req1 = Request({"type": "http", "method": "POST", "path": "/api/v1/chat", "headers": Headers({"x-application-id": "cineku"}).raw})
    assert resolve_tenant_from_request(req1) == "cineku"

    # Test via Path
    req2 = Request({"type": "http", "method": "POST", "path": "/api/v1/owl/chat", "headers": Headers({}).raw})
    assert resolve_tenant_from_request(req2) == "owl"

    req3 = Request({"type": "http", "method": "POST", "path": "/api/v1/hr-corner/chat", "headers": Headers({}).raw})
    assert resolve_tenant_from_request(req3) == "hr-corner"


def test_secret_sanitization_audit():
    """Verify sanitize_log_data scrubs API keys, authorization tokens, and sensitive keys."""
    raw_payload = {
        "x-api-key": "secret-api-key-12345",
        "authorization": "Bearer secret-jwt-token-9999",
        "password": "super-secret-pass",
        "normal_key": "safe_value",
        "nested": {
            "token": "nested-secret-token",
            "user_id": 42,
        }
    }

    sanitized = sanitize_log_data(raw_payload)
    assert sanitized["x-api-key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["normal_key"] == "safe_value"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["user_id"] == 42


def test_error_response_contains_request_id():
    """Verify error responses include request_id in standard error payload."""
    response = client.get("/api/v1/nonexistent-endpoint-xyz")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "request_id" in data["error"]
    assert len(data["error"]["request_id"]) > 0


def test_failure_simulation_401_unauthorized():
    """Failure test: Request with missing or invalid API key returns 401 with request_id."""
    response = client.post(
        "/api/v1/cineku/chat",
        headers={"X-API-Key": "invalid-cineku-key"},
        json={"application": "cineku", "message": "Halo"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "request_id" in data["error"]


def test_failure_simulation_403_tenant_forbidden():
    """Failure test: Cineku API key accessing OWL endpoint returns 403 Forbidden with request_id."""
    response = client.post(
        "/api/v1/owl/chat",
        headers={"X-API-Key": "cineku-secret-api-key"},
        json={"application": "owl", "message": "Halo OWL"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "TENANT_ACCESS_DENIED"
    assert "request_id" in data["error"]


def test_failure_simulation_422_validation_error():
    """Failure test: Invalid payload returns 422 with request_id."""
    response = client.post(
        "/api/v1/owl/chat",
        headers={"X-API-Key": "owl-secret-api-key"},
        json={"invalid_field": "no message field"}
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in data["error"]
