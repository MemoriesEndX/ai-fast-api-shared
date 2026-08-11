import logging
from typing import Dict, Any, Optional
from app.mcp.registry import register_tool
from app.integrations.lms_client import LMSClientService
from app.tools.auth import UserAuthContext

logger = logging.getLogger("ai_service.tools.assessment")
lms_client = LMSClientService()


@register_tool(
    name="get_user_assessments",
    description="Fetch user's assessment and exam score results.",
    input_schema={"user_id": "integer"},
    output_schema={"user_id": "integer", "items": "array"},
    requires_auth=True,
)
async def get_user_assessments(user_id: int, auth_context: Optional[UserAuthContext] = None) -> Dict[str, Any]:
    """Tool #3: Fetch user's assessment and exam results."""
    uid = auth_context.user_id if auth_context else user_id
    assessments = await lms_client.get_user_assessments(uid)
    return assessments
