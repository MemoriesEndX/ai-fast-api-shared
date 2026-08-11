import sys
import time
import uuid
import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

# Configure standard logger
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("ai_service")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to inject X-Request-ID, track processing latency, and emit structured logs."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Request ID tracing
        incoming_request_id = request.headers.get("x-request-id")
        request_id = incoming_request_id if incoming_request_id and len(incoming_request_id) < 64 else str(uuid.uuid4())
        request.state.request_id = request_id

        # Application metadata header
        client_app = request.headers.get("x-application-id", "unknown")

        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000  # in ms
        
        logger.info(
            f"ReqID: {request_id} | Method: {request.method} | Path: {request.url.path} | "
            f"ClientApp: {client_app} | Status: {response.status_code} | "
            f"Duration: {process_time:.2f}ms"
        )
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
