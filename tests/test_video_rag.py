import io

HEADERS = {"X-API-Key": "dev-shared-ai-key-change-in-production"}
DUMMY_VIDEO_BYTES = b"dummy_mp4_header_data_for_video_transcription_test"


def test_video_upload_and_rag_chat(client):
    # 1. Upload Video for OWL tenant
    file_tuple = ("safety_induction_video.mp4", io.BytesIO(DUMMY_VIDEO_BYTES), "video/mp4")
    form_data = {
        "application": "owl",
        "document_id": "2001",
        "title": "Safety Induction Video Module",
        "content_id": "606",
        "version": "1.0",
        "language": "id",
    }
    upload_res = client.post(
        "/api/v1/rag/videos/upload",
        data=form_data,
        files={"file": file_tuple},
        headers=HEADERS,
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["status"] in ("indexed", "already_indexed")
    assert data["application"] == "owl"
    assert data["document_id"] == "2001"
    assert data["filename"] == "safety_induction_video.mp4"

    # 2. Check Video Processing Status
    status_res = client.get(
        "/api/v1/rag/videos/2001/status?application=owl",
        headers=HEADERS,
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["document_id"] == "2001"
    assert status_data["status"] == "completed"

    # 3. Document-Specific Video Chat with Timestamp Source Citations
    chat_payload = {
        "application": "owl",
        "user_id": 123,
        "document_id": "2001",
        "message": "Di mana video menjelaskan penggunaan APD helm keselamatan?"
    }
    chat_res = client.post("/api/v1/chat", json=chat_payload, headers=HEADERS)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["application"] == "owl"
    assert len(chat_data["sources"]) > 0
    source = chat_data["sources"][0]
    assert source["document_id"] == "2001"
    assert source["source_type"] == "video"
    assert "start_time" in source
    assert "end_time" in source


def test_video_reindexing(client):
    file_tuple = ("safety_induction_video_v2.mp4", io.BytesIO(DUMMY_VIDEO_BYTES), "video/mp4")
    form_data = {
        "application": "owl",
        "title": "Safety Induction Video Updated",
        "version": "2.0",
        "language": "id",
    }
    reindex_res = client.post(
        "/api/v1/rag/videos/2001/reindex",
        data=form_data,
        files={"file": file_tuple},
        headers=HEADERS,
    )
    assert reindex_res.status_code == 200
    data = reindex_res.json()
    assert data["status"] in ("indexed", "already_indexed")
    assert data["document_id"] == "2001"


def test_video_tenant_isolation_hr_corner(client):
    # Upload HR Corner video
    file_tuple = ("hr_leave_policy.mp4", io.BytesIO(DUMMY_VIDEO_BYTES), "video/mp4")
    form_data = {
        "application": "hr-corner",
        "document_id": "3001",
        "title": "HR Leave Policy Video",
        "version": "1.0",
    }
    client.post(
        "/api/v1/rag/videos/upload",
        data=form_data,
        files={"file": file_tuple},
        headers=HEADERS,
    )

    # Search in OWL tenant for HR video - should return NO hits from HR Corner
    search_payload = {
        "application": "owl",
        "query": "HR Leave Policy Video",
        "top_k": 5
    }
    res = client.post("/api/v1/rag/search", json=search_payload, headers=HEADERS)
    assert res.status_code == 200
    results = res.json()["results"]
    for item in results:
        assert item["application"] == "owl"
        assert item["document_id"] != "3001"
