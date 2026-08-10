import logging
import sys
import time
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
    """Middleware to log basic request details: method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Application metadata header or context
        client_app = request.headers.get("x-application-id", "unknown")
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000  # in ms
        
        logger.info(
            f"Method: {request.method} | Path: {request.url.path} | "
            f"ClientApp: {client_app} | Status: {response.status_code} | "
            f"Duration: {process_time:.2f}ms"
        )
        
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response
