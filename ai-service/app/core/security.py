from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_security = HTTPBearer(auto_error=False)


async def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_security),
) -> str:
    """Verify provided API key via X-API-Key header or Bearer Token.
    Returns the identified application client identifier if valid.
    """
    token = None
    if header_key:
        token = header_key
    elif bearer:
        token = bearer.credentials

    # If no key configured in settings (development mode without security enforced), allow request
    valid_keys = {
        settings.AI_API_KEY: "shared-ai",
        settings.OWL_AI_API_KEY: "owl",
        settings.HR_AI_API_KEY: "hr-corner",
    }
    
    # Remove empty keys from validation map
    valid_keys = {k: v for k, v in valid_keys.items() if k}

    if not valid_keys:
        return "development"

    if not token or token not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return valid_keys[token]
