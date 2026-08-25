import sys
import time
import uuid
import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.metrics import metrics_registry

# Configure standard logger
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("ai_service")

# Sensitive header & payload keys to strip from logs
SENSITIVE_KEYS = {
    "authorization",
    "x-api-key",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "bearer",
    "user_password",
}


def sanitize_log_data(data: Any) -> Any:
    """Recursively scrub sensitive keys and values from dictionary/list structures."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_log_data(v)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    elif isinstance(data, str):
        # Redact raw API key or Bearer tokens if present in text strings
        if "bearer " in data.lower() or "x-api-key" in data.lower():
            return "[REDACTED_SENSITIVE_TEXT]"
    return data


def resolve_tenant_from_request(request: Request) -> str:
    """Resolve tenant/application ID safely from request header or path prefix."""
    header_app = request.headers.get("x-application-id")
    if header_app and header_app.strip() and header_app != "unknown":
        return header_app.strip().lower()

    path = request.url.path.lower()
    if "/api/v1/owl" in path:
        return "owl"
    elif "/api/v1/hr-corner" in path:
        return "hr-corner"
    elif "/api/v1/public" in path:
        return "public-chat"
    return "shared"


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to inject X-Request-ID, track processing latency, and emit structured logs."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Request ID tracing
        incoming_request_id = request.headers.get("x-request-id")
        request_id = incoming_request_id if incoming_request_id and len(incoming_request_id) < 64 else str(uuid.uuid4())
        request.state.request_id = request_id

        # Application metadata header & path resolution
        client_app = resolve_tenant_from_request(request)

        response = await call_next(request)

        process_time_sec = time.time() - start_time
        process_time_ms = process_time_sec * 1000  # in ms

        # Record request metrics
        status_code = str(response.status_code)
        metrics_registry.inc("ai_requests_total", labels={"application": client_app, "endpoint": request.url.path, "status_code": status_code})
        metrics_registry.observe("ai_request_latency_seconds", process_time_sec, labels={"application": client_app})

        if response.status_code >= 400:
            metrics_registry.inc("ai_request_errors_total", labels={"application": client_app, "status_code": status_code})

        # Structured Log Event Payload
        log_event: Dict[str, Any] = {
            "request_id": request_id,
            "application": client_app,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(process_time_ms, 2),
        }

        # Log structured message
        log_msg = (
            f"ReqID: {request_id} | Method: {request.method} | Path: {request.url.path} | "
            f"ClientApp: {client_app} | Status: {response.status_code} | "
            f"Duration: {process_time_ms:.2f}ms"
        )
        if response.status_code >= 500:
            logger.error(log_msg)
        elif response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

