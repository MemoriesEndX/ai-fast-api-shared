import logging
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ai_service.core.exceptions")


class ErrorCode:
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    FORBIDDEN = "FORBIDDEN"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    INVALID_REQUEST = "INVALID_REQUEST"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_APPLICATION = "UNSUPPORTED_APPLICATION"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    QDRANT_UNAVAILABLE = "QDRANT_UNAVAILABLE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    VIDEO_PROCESSING_FAILED = "VIDEO_PROCESSING_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def format_error_response(code: str, message: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Format standardized public API error payload."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or "unknown",
        }
    }


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Centralized handler for FastAPI / Starlette HTTP Exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    error_code = ErrorCode.INVALID_REQUEST
    message = str(exc.detail)

    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        error_code = ErrorCode.AUTHENTICATION_REQUIRED
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        error_code = ErrorCode.TENANT_ACCESS_DENIED if "tenant" in message.lower() else ErrorCode.FORBIDDEN
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        error_code = ErrorCode.RESOURCE_NOT_FOUND
    elif exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        error_code = ErrorCode.PAYLOAD_TOO_LARGE
    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        error_code = ErrorCode.RATE_LIMITED
    elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        error_code = ErrorCode.AI_SERVICE_UNAVAILABLE
    elif exc.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        error_code = ErrorCode.LLM_TIMEOUT

    # If detail was structured dict (e.g. {"code": "...", "message": "..."})
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("code", error_code)
        message = exc.detail.get("message", str(exc.detail))

    logger.warning(f"HTTPException [{exc.status_code}] Code: {error_code} | Path: {request.url.path} | RequestID: {request_id}")

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(error_code, message, request_id),
        headers=getattr(exc, "headers", None)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Centralized handler for Pydantic Request Validation Errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    errors = exc.errors()
    msg_parts = []
    for err in errors:
        loc = " -> ".join([str(x) for x in err.get("loc", []) if str(x) != "body"])
        msg_parts.append(f"{loc}: {err.get('msg')}" if loc else err.get('msg', 'Validation error'))

    message = "; ".join(msg_parts) if msg_parts else "Request validation failed."
    logger.warning(f"ValidationError | Path: {request.url.path} | RequestID: {request_id} | Detail: {message}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_error_response(ErrorCode.VALIDATION_ERROR, message, request_id)
    )


async def permission_exception_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """Centralized handler for Python PermissionError (Tenant / User isolation breaches)."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"PermissionError | Path: {request.url.path} | RequestID: {request_id} | Detail: {exc}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=format_error_response(ErrorCode.TENANT_ACCESS_DENIED, str(exc), request_id)
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized handler for unexpected server exceptions (prevents internal stack trace leakage)."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled Server Error | Path: {request.url.path} | RequestID: {request_id} | Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(ErrorCode.INTERNAL_ERROR, "An internal server error occurred. Please contact system administrator.", request_id)
    )
