import logging
from typing import Dict, Any, Optional
from app.mcp.registry import register_tool
from app.integrations.lms_client import LMSClientService
from app.tools.auth import UserAuthContext

logger = logging.getLogger("ai_service.tools.content")
lms_client = LMSClientService()


@register_tool(
    name="search_learning_content",
    description="Search active LMS learning contents by keyword query.",
    input_schema={"query": "string", "limit": "integer (default 10)"},
    output_schema={"items": "array"},
    requires_auth=True,
)
async def search_learning_content(query: str, limit: int = 10, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #4: Search learning contents catalog."""
    safe_limit = min(max(1, limit), 20)
    result = await lms_client.search_content(query=query, limit=safe_limit)
    return result


@register_tool(
    name="search_learning_playlist",
    description="Search active LMS training playlists by keyword query.",
    input_schema={"query": "string", "limit": "integer (default 10)"},
    output_schema={"items": "array"},
    requires_auth=True,
)
async def search_learning_playlist(query: str, limit: int = 10, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #5: Search training playlists catalog."""
    safe_limit = min(max(1, limit), 20)
    result = await lms_client.search_playlist(query=query, limit=safe_limit)
    return result


@register_tool(
    name="get_content_detail",
    description="Get metadata details of a specific LMS content by ID.",
    input_schema={"content_id": "integer"},
    output_schema={"id": "integer", "title": "string", "type": "string", "description": "string"},
    requires_auth=True,
)
async def get_content_detail(content_id: int, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #6: Get detail of a specific learning content."""
    detail = await lms_client.get_content_detail(content_id)
    return detail


@register_tool(
    name="get_playlist_detail",
    description="Get detail of a specific LMS training playlist and its child contents.",
    input_schema={"playlist_id": "integer"},
    output_schema={"id": "integer", "title": "string", "contents": "array"},
    requires_auth=True,
)
async def get_playlist_detail(playlist_id: int, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #7: Get detail of a specific training playlist."""
    detail = await lms_client.get_playlist_detail(playlist_id)
    return detail
