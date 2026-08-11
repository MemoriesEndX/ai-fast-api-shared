def test_owl_health_endpoint(client):
    response = client.get("/api/v1/owl/health")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert data["status"] == "connected"
