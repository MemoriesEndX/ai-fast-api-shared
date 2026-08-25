import logging
from typing import Optional, Dict
from fastapi import HTTPException, Header, Request, status
from app.core.config import settings

logger = logging.getLogger("ai_service.core.security")


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Verify API Key / Bearer Token authentication.
    Returns the identified application client identifier ('owl', 'hr-corner', 'public-chat', or 'shared-ai').
    """
    if not settings.AI_API_AUTH_ENABLED:
        return "shared-ai"

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key

    valid_keys: Dict[str, str] = {
        settings.AI_API_KEY: "shared-ai",
        settings.OWL_AI_API_KEY: "owl",
        settings.HR_AI_API_KEY: "hr-corner",
        settings.PUBLIC_CHAT_AI_API_KEY: "public-chat",
    }
    
    # Filter empty or unconfigured keys
    valid_keys = {k: v for k, v in valid_keys.items() if k}

    if not valid_keys:
        return "development"

    if not token or token not in valid_keys:
        logger.warning(f"Unauthorized access attempt with token '{token[:8] if token else 'None'}...'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Invalid or missing API Bearer token."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return valid_keys[token]


def validate_tenant_auth(client_app: str, requested_app: str) -> None:
    """Enforce strict tenant authorization isolation based on API credentials."""
    if not client_app or client_app in ["shared-ai", "development"]:
        return

    client_app_clean = client_app.strip().lower()
    requested_app_clean = requested_app.strip().lower()

    if client_app_clean != requested_app_clean:
        logger.warning(
            f"Tenant isolation breach attempt: '{client_app_clean}' credentials requested '{requested_app_clean}' tenant data."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_ACCESS_DENIED",
                "message": f"Access denied. Application '{client_app_clean}' credentials are not authorized to access '{requested_app_clean}' tenant data."
            }
        )
