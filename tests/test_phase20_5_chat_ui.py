import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_chat_ui_endpoint_serves_html():
    """Test that GET /chat serves the chat UI HTML page with correct headers and contents."""
    response = client.get("/chat")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text

    # Verify structural UI components from requirements
    assert "Shared AI" in content
    assert "AI Service Testing" in content
    assert "chat-health-badge" in content
    assert "chat-empty-state" in content
    assert "Shared AI Assistant" in content
    assert "Halo" in content
    assert "Sarankan resep sederhana" in content
    assert "Jelaskan apa yang bisa kamu lakukan" in content
    assert "chat-message-input" in content
    assert "chat-send-button" in content
    assert "New Chat" in content
    assert "/documentation/assets/css/chat.css" in content
    assert "/documentation/assets/js/chat.js" in content


def test_chat_assets_served():
    """Test that chat CSS and JS assets are successfully accessible via /documentation/assets."""
    css_res = client.get("/documentation/assets/css/chat.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")
    assert "--chat-max-width" in css_res.text

    js_res = client.get("/documentation/assets/js/chat.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers.get("content-type", "")
    assert "renderSafeMarkdown" in js_res.text
    assert "sendMessage" in js_res.text


def test_chat_api_empty_message_validation():
    """Test that sending empty messages to /api/v1/chat fails with 400 Bad Request."""
    response = client.post(
        "/api/v1/chat",
        json={"application": "owl", "user_id": 1, "message": "   "}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "empty" in data["error"]["message"].lower()


def test_chat_api_oversized_message_validation():
    """Test that sending messages over 4000 chars returns 400 Bad Request."""
    response = client.post(
        "/api/v1/chat",
        json={"application": "owl", "user_id": 1, "message": "a" * 4005}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "4000" in data["error"]["message"]


def test_chat_api_security_headers():
    """Test security headers are injected on /chat and /api/v1/chat."""
    res_ui = client.get("/chat")
    assert res_ui.headers.get("x-content-type-options") == "nosniff"
    assert res_ui.headers.get("x-frame-options") == "DENY"
    assert "x-request-id" in res_ui.headers

    res_api = client.post(
        "/api/v1/chat",
        json={"application": "owl", "user_id": 1, "message": "Halo"}
    )
    assert res_api.status_code == 200
    assert res_api.headers.get("x-content-type-options") == "nosniff"
    assert res_api.headers.get("x-frame-options") == "DENY"
    assert "x-request-id" in res_api.headers


def test_chat_api_successful_completion_and_conversation_flow():
    """Test multi-turn chat flow with conversation_id tracking."""
    # First turn
    turn1_res = client.post(
        "/api/v1/chat",
        json={"application": "owl", "user_id": 1, "message": "Halo"}
    )
    assert turn1_res.status_code == 200
    turn1_data = turn1_res.json()
    assert turn1_data["application"] == "owl"
    assert turn1_data["message"]
    assert turn1_data["conversation_id"]
    conv_id = turn1_data["conversation_id"]

    # Second turn maintaining session
    turn2_res = client.post(
        "/api/v1/chat",
        json={
            "application": "owl",
            "user_id": 1,
            "message": "Bisakah kamu menyarankan 3 resep sederhana untuk makan malam?",
            "conversation_id": conv_id
        }
    )
    assert turn2_res.status_code == 200
    turn2_data = turn2_res.json()
    assert turn2_data["conversation_id"] == conv_id
    assert turn2_data["answer"] or turn2_data["message"]
