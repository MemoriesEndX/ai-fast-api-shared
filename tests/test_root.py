def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Shared AI Service"
    assert data["status"] == "running"
    assert "version" in data


def test_documentation_frontend_endpoint(client):
    response = client.get("/documentation/")
    assert response.status_code == 200
    assert "SHARED AI SERVICE" in response.text
    assert "text/html" in response.headers.get("content-type", "")


def test_openapi_json_endpoint(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data

