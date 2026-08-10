def test_hr_corner_health_endpoint(client):
    response = client.get("/api/v1/hr-corner/health")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "hr-corner"
    assert data["status"] == "connected"
