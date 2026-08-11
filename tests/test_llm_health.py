def test_llm_health_endpoint(client):
    response = client.get("/api/v1/health/llm")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["provider"] == "llama_cpp"
    assert "qwen2.5-0.5b" in data["model"]
