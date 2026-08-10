def test_chat_owl_endpoint(client):
    payload = {
        "application": "owl",
        "user_id": 123,
        "message": "Apa tujuan pembelajaran ini?"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert data["provider"] == "llama_cpp"
    assert "qwen2.5-0.5b" in data["model"]
    assert "message" in data


def test_chat_hr_corner_endpoint(client):
    payload = {
        "application": "hr-corner",
        "user_id": 456,
        "message": "Apa fungsi HR Corner?"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "hr-corner"
    assert data["provider"] == "llama_cpp"
    assert "qwen2.5-0.5b" in data["model"]
    assert "message" in data
