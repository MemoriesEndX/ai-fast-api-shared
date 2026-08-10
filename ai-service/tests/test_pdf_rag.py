import io
from tests.test_pdf import SAMPLE_PDF_BYTES

HEADERS = {"X-API-Key": "dev-shared-ai-key-change-in-production"}


def test_pdf_upload_and_rag_chat(client):
    # 1. Upload PDF for OWL tenant
    file_tuple = ("safety_induction.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")
    form_data = {
        "application": "owl",
        "document_id": "1001",
        "title": "Safety Induction SOP",
        "content_id": "505",
        "version": "1.0",
    }
    upload_res = client.post(
        "/api/v1/rag/documents/upload",
        data=form_data,
        files={"file": file_tuple},
        headers=HEADERS,
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["status"] in ("indexed", "already_indexed")
    assert data["application"] == "owl"
    assert data["document_id"] == "1001"
    assert data["filename"] == "safety_induction.pdf"

    # 2. Document-Specific Chat Search
    chat_payload = {
        "application": "owl",
        "user_id": 123,
        "document_id": "1001",
        "message": "Safety Induction LMS Module Page 1"
    }
    chat_res = client.post("/api/v1/chat", json=chat_payload, headers=HEADERS)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["application"] == "owl"
    assert len(chat_data["sources"]) > 0
    assert chat_data["sources"][0]["document_id"] == "1001"
    assert chat_data["sources"][0]["page_start"] == 1


def test_pdf_reindexing(client):
    file_tuple = ("safety_induction_v2.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")
    form_data = {
        "application": "owl",
        "title": "Safety Induction SOP Updated",
        "version": "2.0",
    }
    reindex_res = client.post(
        "/api/v1/rag/documents/1001/reindex",
        data=form_data,
        files={"file": file_tuple},
        headers=HEADERS,
    )
    assert reindex_res.status_code == 200
    data = reindex_res.json()
    assert data["status"] in ("indexed", "already_indexed")
    assert data["document_id"] == "1001"
