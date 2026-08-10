def test_chat_placeholder_endpoint(client):
    payload = {
        "application": "owl",
        "user_id": 123,
        "message": "Apa tujuan pembelajaran ini?"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert data["message"] == "AI service is ready."
    assert data["provider"] == "llama_cpp"
    assert data["model"] is None


def test_chat_hr_corner_endpoint(client):
    payload = {
        "application": "hr-corner",
        "user_id": 456,
        "message": "Bagaimana prosedur pengajuan cuti?"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "hr-corner"
    assert data["message"] == "AI service is ready."
