HEADERS = {"X-API-Key": "dev-shared-ai-key-change-in-production"}


def test_document_indexing_and_search(client):
    # 1. Index document for OWL
    owl_doc = {
        "application": "owl",
        "document_id": "101",
        "title": "Safety Induction LMS",
        "text": "Semua siswa dan instruktur wajib menggunakan Alat Pelindung Diri APD helm dan sepatu keselamatan saat memasuki area laboratorium."
    }
    index_res = client.post("/api/v1/rag/documents/index", json=owl_doc, headers=HEADERS)
    assert index_res.status_code == 200
    assert index_res.json()["status"] == "indexed"
    assert index_res.json()["chunks"] > 0

    # 2. Index document for HR Corner
    hr_doc = {
        "application": "hr-corner",
        "document_id": "202",
        "title": "Leave Policy HR",
        "text": "Pengajuan cuti tahunan dilakukan melalui sistem HR Corner minimal 3 hari sebelum tanggal pelaksanaan cuti."
    }
    index_res_hr = client.post("/api/v1/rag/documents/index", json=hr_doc, headers=HEADERS)
    assert index_res_hr.status_code == 200

    # 3. Vector Search OWL
    search_owl = {
        "application": "owl",
        "query": "Alat Pelindung Diri APD helm keselamatan",
        "top_k": 3
    }
    search_res = client.post("/api/v1/rag/search", json=search_owl, headers=HEADERS)
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert len(results) > 0
    doc_ids = [str(r["document_id"]) for r in results]
    assert "101" in doc_ids


    # 4. Multi-Tenant Application Isolation Verification
    # OWL Search must NOT return HR Corner documents
    for res in results:
        assert res["application"] == "owl"
        assert res["document_id"] != "202"


def test_tenant_isolation_hr_corner(client):
    # Ensure HR document 202 is indexed
    hr_doc = {
        "application": "hr-corner",
        "document_id": "202",
        "title": "Leave Policy HR",
        "text": "Pengajuan cuti tahunan dilakukan melalui sistem HR Corner minimal 3 hari sebelum tanggal pelaksanaan cuti."
    }
    client.post("/api/v1/rag/documents/index", json=hr_doc, headers=HEADERS)

    # Search HR Corner tenant
    search_hr = {
        "application": "hr-corner",
        "query": "prosedur pengajuan cuti",
        "top_k": 3
    }
    search_res = client.post("/api/v1/rag/search", json=search_hr, headers=HEADERS)
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert len(results) > 0
    hr_doc_ids = [str(r["document_id"]) for r in results]
    assert "202" in hr_doc_ids


    # HR Search must NOT return OWL documents
    for res in results:
        assert res["application"] == "hr-corner"
        assert res["document_id"] != "101"



def test_document_deletion(client):
    # Delete document 101 from OWL tenant
    del_res = client.delete("/api/v1/rag/documents/101?application=owl", headers=HEADERS)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


def test_no_context_rag_chat(client):
    # Query an unindexed application tenant
    chat_payload = {
        "application": "future-app",
        "user_id": 999,
        "message": "Berapa gaji presiden?"
    }
    chat_res = client.post("/api/v1/chat", json=chat_payload, headers=HEADERS)
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["application"] == "future-app"
    assert "Informasi tersebut tidak ditemukan" in data["message"]
    assert data["sources"] == []
