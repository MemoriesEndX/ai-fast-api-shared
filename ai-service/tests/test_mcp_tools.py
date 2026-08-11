import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.mcp.registry import tool_registry
from app.mcp.server import mcp_server
from app.tools.auth import UserAuthContext
from app.core.config import settings

client = TestClient(app)
owl_headers = {"X-API-Key": settings.OWL_AI_API_KEY}
hr_headers = {"X-API-Key": settings.HR_AI_API_KEY}


def test_tool_registry_registration():
    """Test that all 10 MCP LMS & RAG tools are properly registered."""
    tools = tool_registry.list_tools()
    tool_names = [t.name for t in tools]
    expected_tools = [
        "get_user_learning_profile",
        "get_learning_progress",
        "get_user_assessments",
        "search_learning_content",
        "search_learning_playlist",
        "get_content_detail",
        "get_playlist_detail",
        "get_learning_recommendations",
        "search_pdf_knowledge",
        "search_video_transcript",
    ]
    for expected in expected_tools:
        assert expected in tool_names, f"Missing tool '{expected}' in registry"
    assert len(tool_names) >= 10


@pytest.mark.asyncio
async def test_tool_1_get_user_learning_profile():
    """Test Tool #1: get_user_learning_profile."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_user_learning_profile", {"user_id": 123}, auth_context=auth)
    assert "error" not in result
    assert result["user_id"] == 123
    assert result["division"] == "Production"
    assert result["position"] == "Supervisor"
    # Ensure sensitive fields are excluded
    assert "password" not in result
    assert "token" not in result


@pytest.mark.asyncio
async def test_tool_2_get_learning_progress():
    """Test Tool #2: get_learning_progress."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_learning_progress", {"user_id": 123}, auth_context=auth)
    assert "error" not in result
    assert result["user_id"] == 123
    assert "items" in result
    assert len(result["items"]) > 0
    assert result["items"][0]["content_id"] == 101
    assert result["items"][0]["progress"] == 100


@pytest.mark.asyncio
async def test_tool_3_get_user_assessments():
    """Test Tool #3: get_user_assessments."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_user_assessments", {"user_id": 123}, auth_context=auth)
    assert "error" not in result
    assert result["user_id"] == 123
    assert "items" in result
    assert result["items"][0]["score"] == 55.0


@pytest.mark.asyncio
async def test_tool_4_search_learning_content():
    """Test Tool #4: search_learning_content."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("search_learning_content", {"query": "safety", "limit": 5}, auth_context=auth)
    assert "error" not in result
    assert "items" in result
    assert len(result["items"]) > 0
    assert "title" in result["items"][0]


@pytest.mark.asyncio
async def test_tool_5_search_learning_playlist():
    """Test Tool #5: search_learning_playlist."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("search_learning_playlist", {"query": "safety", "limit": 5}, auth_context=auth)
    assert "error" not in result
    assert "items" in result
    assert len(result["items"]) > 0


@pytest.mark.asyncio
async def test_tool_6_get_content_detail():
    """Test Tool #6: get_content_detail."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_content_detail", {"content_id": 101}, auth_context=auth)
    assert "error" not in result
    assert result["id"] == 101
    assert "Safety Induction" in result["title"]


@pytest.mark.asyncio
async def test_tool_7_get_playlist_detail():
    """Test Tool #7: get_playlist_detail."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_playlist_detail", {"playlist_id": 103}, auth_context=auth)
    assert "error" not in result
    assert result["id"] == 103
    assert "contents" in result


@pytest.mark.asyncio
async def test_tool_8_get_learning_recommendations():
    """Test Tool #8: get_learning_recommendations (Phase 6 Integration)."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("get_learning_recommendations", {"user_id": 123, "limit": 3}, auth_context=auth)
    assert "error" not in result
    assert result["application"] == "owl"
    assert len(result["recommendations"]) > 0


@pytest.mark.asyncio
async def test_tool_9_search_pdf_knowledge():
    """Test Tool #9: search_pdf_knowledge (Phase 4 Integration)."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("search_pdf_knowledge", {"query": "APD safety rules", "top_k": 3}, auth_context=auth)
    assert "error" not in result
    assert "results" in result
    assert len(result["results"]) > 0
    assert "page_start" in result["results"][0]


@pytest.mark.asyncio
async def test_tool_10_search_video_transcript():
    """Test Tool #10: search_video_transcript (Phase 5 Integration)."""
    auth = UserAuthContext(user_id=123, application="owl")
    result = await mcp_server.execute_tool("search_video_transcript", {"query": "demo penggunaan APD", "top_k": 3}, auth_context=auth)
    assert "error" not in result
    assert "results" in result
    assert len(result["results"]) > 0
    assert "start_time" in result["results"][0]


@pytest.mark.asyncio
async def test_security_cross_user_access_blocked():
    """Security Test: User A (123) requesting User B's (999) records must be blocked with PERMISSION_DENIED."""
    auth_user_a = UserAuthContext(user_id=123, role="User", application="owl")
    result = await mcp_server.execute_tool("get_learning_progress", {"user_id": 999}, auth_context=auth_user_a)
    assert "error" in result
    assert result["error"]["code"] == "PERMISSION_DENIED"
    assert "User ID 123 is not authorized" in result["error"]["message"]


@pytest.mark.asyncio
async def test_security_hr_corner_owl_tool_access_blocked():
    """Security Test: Tenant HR Corner accessing OWL LMS tools must be blocked."""
    auth_hr = UserAuthContext(user_id=123, role="User", application="hr-corner")
    result = await mcp_server.execute_tool("get_user_learning_profile", {"user_id": 123}, auth_context=auth_hr)
    assert "error" in result
    assert result["error"]["code"] == "PERMISSION_DENIED"
    assert "hr-corner" in result["error"]["message"]


@pytest.mark.asyncio
async def test_security_sql_injection_prevention():
    """Security Test: Ensure malicious SQL strings pass cleanly without database execution."""
    auth = UserAuthContext(user_id=123, application="owl")
    malicious_query = "safety' UNION SELECT password FROM users --"
    result = await mcp_server.execute_tool("search_learning_content", {"query": malicious_query, "limit": 5}, auth_context=auth)
    assert "error" not in result
    assert "items" in result
    # Output must be sanitized JSON list, no raw SQL error thrown


def test_debug_endpoint_get_tools():
    """Test GET /api/v1/tools debug endpoint."""
    response = client.get("/api/v1/tools", headers=owl_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_tools"] >= 10
    assert len(data["tools"]) >= 10


def test_chat_with_mcp_tool_execution():
    """Test End-to-End Chat integration using MCP tools."""
    payload = {
        "application": "owl",
        "user_id": 123,
        "message": "Pembelajaran apa yang cocok untuk saya?",
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "owl"
    assert "message" in data
    assert "tools_used" in data
