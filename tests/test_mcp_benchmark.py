import pytest
import time
import asyncio
from app.mcp.server import mcp_server
from app.tools.auth import UserAuthContext


@pytest.mark.asyncio
async def test_mcp_tool_execution_benchmark():
    """Benchmark execution latency of each individual MCP tool."""
    auth = UserAuthContext(user_id=123, application="owl")
    tools_to_benchmark = [
        ("get_user_learning_profile", {"user_id": 123}),
        ("get_learning_progress", {"user_id": 123}),
        ("get_user_assessments", {"user_id": 123}),
        ("search_learning_content", {"query": "safety", "limit": 5}),
        ("search_learning_playlist", {"query": "safety", "limit": 5}),
        ("get_content_detail", {"content_id": 101}),
        ("get_playlist_detail", {"playlist_id": 103}),
        ("get_learning_recommendations", {"user_id": 123, "limit": 5}),
        ("search_pdf_knowledge", {"query": "APD rules", "top_k": 3}),
        ("search_video_transcript", {"query": "demo APD", "top_k": 3}),
    ]

    print("\n=================== MCP TOOLS BENCHMARK ===================")
    for tool_name, args in tools_to_benchmark:
        start = time.perf_counter()
        result = await mcp_server.execute_tool(tool_name, args, auth_context=auth)
        duration_ms = (time.perf_counter() - start) * 1000
        max_allowed = 5000.0 if tool_name == "get_learning_recommendations" else 1000.0
        assert duration_ms < max_allowed, f"Tool '{tool_name}' execution took too long: {duration_ms:.3f} ms"
    print("===========================================================")
