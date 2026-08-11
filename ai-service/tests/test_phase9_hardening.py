import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

OWL_HEADERS = {"Authorization": "Bearer owl-secret-api-key"}
HR_HEADERS = {"Authorization": "Bearer hr-corner-secret-api-key"}
SHARED_HEADERS = {"Authorization": "Bearer dev-shared-ai-key-change-in-production"}
INVALID_HEADERS = {"Authorization": "Bearer invalid-secret-token"}


def test_auth_missing_token():
    """Verify missing API Bearer token returns 401 AUTHENTICATION_REQUIRED."""
    res = client.post("/api/v1/chat", json={"application": "owl", "message": "Hello"})
    assert res.status_code == 401
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] in ("AUTHENTICATION_REQUIRED", "INVALID_TOKEN")
    assert "request_id" in data["error"]


def test_auth_invalid_token():
    """Verify invalid API Bearer token returns 401 AUTHENTICATION_REQUIRED."""
    res = client.post("/api/v1/chat", json={"application": "owl", "message": "Hello"}, headers=INVALID_HEADERS)
    assert res.status_code == 401
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] in ("AUTHENTICATION_REQUIRED", "INVALID_TOKEN")


def test_tenant_isolation_owl_requesting_hr_corner():
    """Verify OWL credential requesting HR-Corner application tenant returns 403 TENANT_ACCESS_DENIED."""
    payload = {"application": "hr-corner", "message": "What is HR leave policy?"}
    res = client.post("/api/v1/chat", json=payload, headers=OWL_HEADERS)
    assert res.status_code == 403
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "TENANT_ACCESS_DENIED"


def test_tenant_isolation_hr_corner_requesting_owl():
    """Verify HR-Corner credential requesting OWL application tenant returns 403 TENANT_ACCESS_DENIED."""
    payload = {"application": "owl", "message": "What is LMS progress?"}
    res = client.post("/api/v1/chat", json=payload, headers=HR_HEADERS)
    assert res.status_code == 403
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "TENANT_ACCESS_DENIED"


def test_shared_token_authorized_for_both_tenants():
    """Verify Shared AI credential can access both OWL and HR-Corner application tenants."""
    owl_res = client.post("/api/v1/chat", json={"application": "owl", "message": "Test OWL"}, headers=SHARED_HEADERS)
    assert owl_res.status_code == 200

    hr_res = client.post("/api/v1/chat", json={"application": "hr-corner", "message": "Test HR"}, headers=SHARED_HEADERS)
    assert hr_res.status_code == 200


def test_request_id_tracing():
    """Verify X-Request-ID propagation from client to response headers and error payload."""
    custom_id = "trace-uuid-1234-abcd"
    res = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_id

    # Test propagation in error response payload
    err_res = client.post("/api/v1/chat", json={"application": "owl", "message": "Hello"}, headers={"X-Request-ID": custom_id})
    assert err_res.status_code == 401
    err_data = err_res.json()
    assert err_data["error"]["request_id"] == custom_id


def test_path_traversal_blocking():
    """Verify path traversal attack in document upload is blocked."""
    file_tuple = ("file.pdf", io.BytesIO(b"dummy pdf content"), "application/pdf")
    form_data = {
        "application": "owl",
        "document_id": "../../etc/passwd",
        "title": "Malicious Upload",
    }
    res = client.post(
        "/api/v1/rag/documents/upload",
        data=form_data,
        files={"file": file_tuple},
        headers=SHARED_HEADERS,
    )
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_invalid_file_extension_upload():
    """Verify uploading forbidden file extension returns 400 INVALID_FILE_TYPE."""
    file_tuple = ("script.exe", io.BytesIO(b"binary data"), "application/octet-stream")
    form_data = {
        "application": "owl",
        "document_id": "1002",
        "title": "Executable Test",
    }
    res = client.post(
        "/api/v1/rag/documents/upload",
        data=form_data,
        files={"file": file_tuple},
        headers=SHARED_HEADERS,
    )
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_FILE_TYPE"


def test_liveness_and_readiness_probes():
    """Verify /health (liveness) and /ready (readiness) probes."""
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    ready_res = client.get("/ready")
    assert ready_res.status_code == 200
    data = ready_res.json()
    assert data["status"] == "ready"
    assert "dependencies" in data


def test_chat_message_length_limit():
    """Verify huge prompt message exceeding max payload limit returns 400 INVALID_REQUEST."""
    huge_message = "A" * 5000
    res = client.post("/api/v1/chat", json={"application": "owl", "message": huge_message}, headers=SHARED_HEADERS)
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REQUEST"
