HEADERS = {"X-API-Key": "dev-shared-ai-key-change-in-production"}


def test_chat_owl_unindexed(client):
    payload = {
        "application": "owl",
        "user_id": 123,
        "message": "Apa tujuan pembelajaran ini?"
    }
    response = client.post("/api/v1/chat", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert "Informasi tersebut tidak ditemukan" in data["message"]
    assert isinstance(data["sources"], list)


def test_chat_hr_corner_unindexed(client):
    payload = {
        "application": "hr-corner",
        "user_id": 456,
        "message": "Apa fungsi HR Corner?"
    }
    response = client.post("/api/v1/chat", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "hr-corner"
    assert "Informasi tersebut tidak ditemukan" in data["message"]
    assert isinstance(data["sources"], list)
