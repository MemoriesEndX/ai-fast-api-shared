def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Shared AI Service"
    assert data["status"] == "running"
    assert "version" in data
