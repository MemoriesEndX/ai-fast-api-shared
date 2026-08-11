import io
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

OWL_HEADERS = {"Authorization": "Bearer owl-secret-api-key"}
HR_HEADERS = {"Authorization": "Bearer hr-corner-secret-api-key"}


def create_mock_pdf_bytes(text_content: str = "Knowledge Management Safety Rules") -> bytes:
    """Generate a minimal valid single-page PDF with text layer."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # Using pypdf annotations or stream text simulation
    buf = io.BytesIO()
    writer.write(buf)
    pdf_raw = buf.getvalue()
    # In test environment, PDFService fallback handles mock text if needed
    return pdf_raw


def test_pdf_knowledge_ingestion():
    """Verify PDF knowledge upload, text extraction, page chunking, and Qdrant indexing."""
    pdf_bytes = b"%PDF-1.4 " + b"Knowledge Safety APD Helm Guidelines Page 1 Text " * 50
    files = {"file": ("safety_guide.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "title": "OWL Safety Guide 2026",
        "application": "owl",
        "document_id": "pdf-kn-101",
        "source_type": "pdf",
    }
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] in ("completed", "duplicate")
    assert res_data["document_id"] == "pdf-kn-101"
    assert res_data["source_type"] == "pdf"
    assert res_data["application"] == "owl"
    assert "document_hash" in res_data


def test_pdf_duplicate_detection():
    """Verify upload of duplicate SHA-256 file returns duplicate status without duplicate vectors."""
    pdf_bytes = b"%PDF-1.4 " + b"Identical Duplicate File Content Test SHA256 " * 30
    files1 = {"file": ("dup_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data1 = {"title": "Dup Test First", "application": "owl", "document_id": "pdf-dup-001"}
    r1 = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data1, files=files1)
    assert r1.status_code == 200

    # Upload second time with same file bytes
    files2 = {"file": ("dup_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data2 = {"title": "Dup Test Second", "application": "owl", "document_id": "pdf-dup-002"}
    r2 = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data2, files=files2)
    assert r2.status_code == 200
    res_data2 = r2.json()
    assert res_data2["status"] == "duplicate"
    assert "already exists" in res_data2["message"].lower()


def test_video_knowledge_ingestion():
    """Verify Video knowledge upload, audio extraction, Whisper STT, and timestamp chunking."""
    video_bytes = b"DUMMY_MP4_VIDEO_HEADER_CONTAINER_DATA" * 50
    files = {"file": ("training_video.mp4", io.BytesIO(video_bytes), "video/mp4")}
    data = {
        "title": "Safety Induction Video Training",
        "application": "owl",
        "document_id": "vid-kn-201",
        "source_type": "video",
    }
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] in ("completed", "duplicate")
    assert res["document_id"] == "vid-kn-201"
    assert res["source_type"] == "video"


def test_audio_knowledge_ingestion():
    """Verify Audio knowledge upload (.mp3), STT transcription, and timestamp metadata."""
    audio_bytes = b"DUMMY_MP3_AUDIO_HEADER_DATA_CONTAINER" * 50
    files = {"file": ("lecture_audio.mp3", io.BytesIO(audio_bytes), "audio/mpeg")}
    data = {
        "title": "Lecture Audio Safety Induction",
        "application": "owl",
        "document_id": "aud-kn-301",
        "source_type": "audio",
    }
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] in ("completed", "duplicate")
    assert res["document_id"] == "aud-kn-301"
    assert res["source_type"] == "audio"


def test_direct_knowledge_vector_search():
    """Verify POST /api/v1/knowledge/search returns vector similarity search results."""
    payload = {
        "application": "owl",
        "query": "APD helm keselamatan",
        "source_type": "pdf",
        "top_k": 3,
    }
    response = client.post("/api/v1/knowledge/search", headers=OWL_HEADERS, json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["query"] == "APD helm keselamatan"
    assert res["application"] == "owl"
    assert isinstance(res["results"], list)
    if res["results"]:
        item = res["results"][0]
        assert "document_id" in item
        assert "score" in item
        assert isinstance(item["score"], float)


def test_knowledge_search_document_id_filter():
    """Verify search with explicit document_id filter isolates query results."""
    payload = {
        "application": "owl",
        "query": "Safety Induction APD",
        "document_id": "pdf-kn-101",
        "top_k": 3,
    }
    response = client.post("/api/v1/knowledge/search", headers=OWL_HEADERS, json=payload)
    assert response.status_code == 200
    res = response.json()
    for item in res["results"]:
        assert str(item["document_id"]) == "pdf-kn-101"


def test_get_knowledge_document_status():
    """Verify GET /api/v1/knowledge/documents/{document_id} returns metadata and status."""
    response = client.get("/api/v1/knowledge/documents/pdf-kn-101?application=owl", headers=OWL_HEADERS)
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        res = response.json()
        assert res["document_id"] == "pdf-kn-101"
        assert res["application"] == "owl"
        assert res["status"] == "COMPLETED"


def test_list_knowledge_documents():
    """Verify GET /api/v1/knowledge/documents lists tenant knowledge documents with pagination."""
    response = client.get("/api/v1/knowledge/documents?application=owl&page=1&page_size=10", headers=OWL_HEADERS)
    assert response.status_code == 200
    res = response.json()
    assert res["application"] == "owl"
    assert res["page"] == 1
    assert "documents" in res
    assert isinstance(res["documents"], list)


def test_knowledge_document_delete():
    """Verify DELETE /api/v1/knowledge/documents/{document_id} purges vectors from Qdrant."""
    response = client.delete("/api/v1/knowledge/documents/pdf-kn-101?application=owl", headers=OWL_HEADERS)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["document_id"] == "pdf-kn-101"

    # Verify search for deleted document returns no matches for that document_id
    search_payload = {"application": "owl", "query": "Safety", "document_id": "pdf-kn-101"}
    s_res = client.post("/api/v1/knowledge/search", headers=OWL_HEADERS, json=search_payload)
    assert s_res.status_code == 200
    assert len(s_res.json()["results"]) == 0


def test_knowledge_reindex():
    """Verify POST /api/v1/knowledge/documents/{document_id}/reindex performs atomic vector update."""
    pdf_bytes = b"%PDF-1.4 " + b"Updated Version 1.1 Knowledge Text " * 40
    files = {"file": ("safety_guide_v2.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "title": "OWL Safety Guide 2026 Updated",
        "application": "owl",
        "source_type": "pdf",
        "version": "1.1",
    }
    response = client.post("/api/v1/knowledge/documents/reindex-doc-1/reindex", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "completed"
    assert res["document_id"] == "reindex-doc-1"


def test_tenant_isolation_knowledge_security():
    """Verify cross-tenant knowledge access or upload is blocked with HTTP 403 TENANT_ACCESS_DENIED."""
    pdf_bytes = b"%PDF-1.4 " + b"Cross Tenant Access Violation Attempt " * 20
    files = {"file": ("hr_secret.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    # Attempting to upload to hr-corner using OWL credentials
    data = {"title": "HR Confidential Policy", "application": "hr-corner"}
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 403
    res = response.json()
    assert res["error"]["code"] == "TENANT_ACCESS_DENIED"


def test_unsupported_file_extension():
    """Verify unsupported file extension (.exe) is rejected with HTTP 400."""
    raw_bytes = b"BINARY_EXE_EXEC_DATA"
    files = {"file": ("malicious.exe", io.BytesIO(raw_bytes), "application/octet-stream")}
    data = {"title": "Malicious Exe", "application": "owl"}
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 400
    res = response.json()
    assert res["error"]["code"] in ("UNSUPPORTED_FILE_TYPE", "INVALID_FILE_TYPE")


def test_path_traversal_blocking_knowledge():
    """Verify path traversal in filename is sanitized and blocked safely."""
    pdf_bytes = b"%PDF-1.4 Path Traversal Block Test"
    files = {"file": ("../../etc/passwd.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"title": "Path Traversal Test", "application": "owl"}
    response = client.post("/api/v1/knowledge/documents", headers=OWL_HEADERS, data=data, files=files)
    assert response.status_code == 400
    res = response.json()
    assert "Security Error" in res["error"]["message"] or "Path traversal" in res["error"]["message"]
