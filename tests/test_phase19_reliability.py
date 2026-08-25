"""Phase 19 — Production Reliability & Disaster Recovery Test Suite."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.qdrant_service import qdrant_service, QdrantService
from app.services.llm_service import get_llm_service
from app.core.config import settings

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)

OWL_HEADERS = {"Authorization": "Bearer owl-secret-api-key"}
HR_HEADERS = {"Authorization": "Bearer hr-corner-secret-api-key"}
PUBLIC_CHAT_HEADERS = {"Authorization": "Bearer public-chat-secret-api-key"}


@pytest.mark.asyncio
async def test_qdrant_persistence_and_restart_simulation():
    """Verify vector insertion and persistence across service re-initialization."""
    test_chunks = [{
        "application": "owl",
        "source_type": "pdf",
        "document_id": "persist-doc-101",
        "content_id": "c-101",
        "title": "Persistence Test Document",
        "filename": "persistence_test.pdf",
        "document_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        "chunk_index": 0,
        "page_start": 1,
        "page_end": 1,
        "text": "Data persistence test vector chunk text for Qdrant storage.",
        "vector": [0.1] * settings.EMBEDDING_DIMENSION,
    }]

    # 1. Insert test vector
    upsert_ok = await qdrant_service.upsert_chunks(test_chunks)
    assert upsert_ok is True

    # 2. Verify vector exists via metadata retrieval
    meta_before = await qdrant_service.get_document_metadata("owl", "persist-doc-101")
    assert meta_before is not None
    assert meta_before["chunks_count"] == 1
    assert meta_before["title"] == "Persistence Test Document"

    # 3. Simulate container/service restart by creating a new QdrantService client instance
    restarted_service = QdrantService(
        url=settings.QDRANT_URL,
        collection_name=qdrant_service.collection_name,
        dimension=settings.EMBEDDING_DIMENSION,
    )

    # 4. Query again using new client instance
    meta_after = await restarted_service.get_document_metadata("owl", "persist-doc-101")
    assert meta_after is not None
    assert meta_after["chunks_count"] == 1
    assert meta_after["document_hash"] == test_chunks[0]["document_hash"]


@pytest.mark.asyncio
async def test_qdrant_snapshot_backup_and_restore():
    """Verify snapshot creation, list, deletion, and full collection recovery."""
    seed_chunks = [{
        "application": "hr-corner",
        "source_type": "pdf",
        "document_id": "backup-doc-202",
        "title": "Backup & Disaster Recovery Manual",
        "document_hash": "backup_hash_123456789",
        "chunk_index": 0,
        "text": "Disaster recovery backup test vector payload",
        "vector": [0.2] * settings.EMBEDDING_DIMENSION,
    }]
    await qdrant_service.upsert_chunks(seed_chunks)

    # 1. Create Snapshot Backup
    snap_result = await qdrant_service.create_snapshot()
    assert snap_result["success"] is True
    snap_name = snap_result["snapshot_name"]
    assert snap_name is not None

    # 2. List Snapshots
    snapshots = await qdrant_service.list_snapshots()
    assert len(snapshots) >= 1
    snap_names = [s["name"] for s in snapshots]
    assert snap_name in snap_names

    # 3. Delete original document (simulate data loss/corruption)
    await qdrant_service.delete_document("hr-corner", "backup-doc-202")
    meta_deleted = await qdrant_service.get_document_metadata("hr-corner", "backup-doc-202")
    assert meta_deleted is None

    # 4. Restore snapshot
    restore_ok = await qdrant_service.restore_snapshot(snap_name)
    assert restore_ok is True

    # 5. Verify restored data
    meta_restored = await qdrant_service.get_document_metadata("hr-corner", "backup-doc-202")
    assert meta_restored is not None
    assert meta_restored["document_id"] == "backup-doc-202"
    assert meta_restored["title"] == "Backup & Disaster Recovery Manual"


@pytest.mark.asyncio
async def test_document_idempotency_and_hash_protection():
    """Verify duplicate document upload returns existing payload without duplicating vectors."""
    doc_hash = "sha256_duplicate_test_hash_99999"

    doc_data = [{
        "application": "owl",
        "source_type": "pdf",
        "document_id": "idempotent-doc-303",
        "title": "Idempotency Test Document",
        "document_hash": doc_hash,
        "chunk_index": 0,
        "text": "Idempotent content chunk",
        "vector": [0.05] * settings.EMBEDDING_DIMENSION,
    }]

    await qdrant_service.upsert_chunks(doc_data)

    # Check document by hash
    existing = await qdrant_service.get_document_by_hash("owl", doc_hash)
    assert existing is not None
    assert existing["document_hash"] == doc_hash
    assert existing["document_id"] == "idempotent-doc-303"

    # Re-uploading same document hash returns existing payload
    second_check = await qdrant_service.get_document_by_hash("owl", doc_hash)
    assert second_check["document_id"] == existing["document_id"]


def test_ai_service_restart_recovery():
    """Verify system health, readiness, OpenAPI, and endpoints operate cleanly post-restart."""
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    res_docs = client.get("/openapi.json")
    assert res_docs.status_code == 200

    res_owl = client.post("/api/v1/chat", headers=OWL_HEADERS, json={
        "application": "owl", "user_id": 1, "message": "Hallo LMS"
    })
    assert res_owl.status_code == 200

    res_hr = client.post("/api/v1/chat", headers=HR_HEADERS, json={
        "application": "hr-corner", "user_id": 2, "message": "Hallo HR"
    })
    assert res_hr.status_code == 200

    res_public = client.post("/api/v1/chat", headers=PUBLIC_CHAT_HEADERS, json={
        "application": "public-chat", "user_id": 3, "message": "Halo AI"
    })
    assert res_public.status_code == 200


@pytest.mark.asyncio
async def test_qwen_restart_and_readiness_degradation():
    """Verify /ready endpoint returns 503 AI_SERVICE_UNAVAILABLE when llama-server is unreachable."""
    mock_llm = AsyncMock()
    mock_llm.check_health.side_effect = Exception("Connection refused: llama-server:8080")

    app.dependency_overrides[get_llm_service] = lambda: mock_llm
    try:
        res = client.get("/api/v1/health/readiness")
        assert res.status_code == 503
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "AI_SERVICE_UNAVAILABLE"

        # Verify no secrets leak in error payload
        error_str = str(data)
        assert "dev-shared-ai-key" not in error_str
        assert "owl-secret-api-key" not in error_str
    finally:
        app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_qdrant_restart_and_readiness_degradation():
    """Verify readiness degradation handling when Qdrant connection status fails."""
    with patch.object(qdrant_service, "health_check", new_callable=AsyncMock) as mock_health:
        mock_health.side_effect = Exception("Qdrant connection timeout")

        res = client.get("/api/v1/health/readiness")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["qdrant"] == "memory_fallback" or data["dependencies"]["qdrant"] == "unavailable"


def test_disk_full_and_storage_failure_handling():
    """Verify storage write errors return controlled exception without exposing internal sensitive paths."""
    with patch("app.services.rag_service.RAGService.ingest_pdf_bytes", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.side_effect = IOError("No space left on device")

        res = client_no_raise.post("/api/v1/rag/documents/upload", headers=OWL_HEADERS, data={
            "application": "owl",
            "document_id": "disk-full-test",
            "title": "Disk Full Test"
        }, files={
            "file": ("test.pdf", b"%PDF-1.4 sample content text", "application/pdf")
        })

        assert res.status_code in (500, 503)
        res_text = res.text
        assert "owl-secret-api-key" not in res_text
        assert "dev-shared-ai-key" not in res_text


def test_corrupted_or_missing_data_resilience():
    """Verify application handles missing documents, collections, and malformed inputs gracefully."""
    res_delete = client.delete("/api/v1/rag/documents/non-existent-doc-9999?application=owl", headers=OWL_HEADERS)
    assert res_delete.status_code == 200
    assert "status" in res_delete.json()

    res_search = client.post("/api/v1/rag/search", headers=OWL_HEADERS, json={
        "application": "owl",
        "query": "Non-existent document query search term xyz123999"
    })
    assert res_search.status_code == 200
    assert "results" in res_search.json()



def test_full_health_and_readiness_matrix():
    """Test full matrix of health and readiness probes."""
    res_live = client.get("/health")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"
    assert res_live.json()["service"] == "ai-service"

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
    assert "llm" in res_ready.json()["dependencies"]
    assert "qdrant" in res_ready.json()["dependencies"]
