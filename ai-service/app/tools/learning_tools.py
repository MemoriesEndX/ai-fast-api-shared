import logging
from typing import Dict, Any, Optional
from app.mcp.registry import register_tool
from app.integrations.lms_client import LMSClientService
from app.tools.auth import UserAuthContext

logger = logging.getLogger("ai_service.tools.learning")
lms_client = LMSClientService()


@register_tool(
    name="get_user_learning_profile",
    description="Fetch authenticated user's LMS profile (division, position, department, team).",
    input_schema={"user_id": "integer"},
    output_schema={"user_id": "integer", "division": "string", "position": "string"},
    requires_auth=True,
)
async def get_user_learning_profile(user_id: int, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #1: Fetch authenticated user's learning profile."""
    # Ensure user_id matches authenticated context if provided
    uid = auth_context.user_id if auth_context else user_id
    profile = await lms_client.get_user_profile(uid)
    return profile


@register_tool(
    name="get_learning_progress",
    description="Fetch user's LMS course completion and progress items.",
    input_schema={"user_id": "integer"},
    output_schema={"user_id": "integer", "items": "array"},
    requires_auth=True,
)
async def get_learning_progress(user_id: int, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #2: Fetch user's course completion and learning progress."""
    uid = auth_context.user_id if auth_context else user_id
    progress = await lms_client.get_learning_progress(uid)
    return progress
