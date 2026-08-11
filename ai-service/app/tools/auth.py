import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_service.tools.auth")


class UserAuthContext(BaseModel):
    """Authenticated User Context derived from JWT / API Credentials.
    
    CRITICAL SECURITY MANDATE:
    User identity MUST originate from authenticated request headers/tokens,
    and MUST NEVER be trusted directly from unauthenticated LLM prompt text.
    """
    user_id: int
    name: Optional[str] = "Authenticated User"
    division: Optional[str] = "General"
    position: Optional[str] = "Employee"
    role: str = Field(default="User", description="User role: User, Supervisor, Admin, SuperAdmin")
    application: str = Field(default="owl", description="Tenant application: owl or hr-corner")


class ToolAuthorizationService:
    """Authorization validator for tool executions."""

    @staticmethod
    def validate_tenant_access(auth_context: UserAuthContext, required_application: str = "owl") -> None:
        """Enforce strict tenant isolation."""
        if auth_context.application != required_application:
            logger.warning(
                f"Tenant isolation breach attempt: application '{auth_context.application}' requested '{required_application}' tool."
            )
            raise PermissionError(
                f"Access denied. Application '{auth_context.application}' is not authorized for '{required_application}' LMS tools."
            )

    @staticmethod
    def validate_user_access(auth_context: UserAuthContext, target_user_id: int) -> None:
        """Enforce strict user-level data isolation (User A cannot access User B's profile/progress)."""
        is_admin = auth_context.role in ["Admin", "SuperAdmin"]
        if auth_context.user_id != target_user_id and not is_admin:
            logger.warning(
                f"Cross-user access denied: User {auth_context.user_id} attempted to access data for User {target_user_id}."
            )
            raise PermissionError(
                f"Access denied. User ID {auth_context.user_id} is not authorized to access records for User ID {target_user_id}."
            )
