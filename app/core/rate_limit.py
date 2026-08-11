import time
import logging
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status
from app.core.config import settings

logger = logging.getLogger("ai_service.core.rate_limit")


class RateLimiter:
    """In-memory sliding window rate limiter per client IP / API credential."""

    def __init__(self):
        # Maps bucket_key -> List[timestamp]
        self._history: Dict[str, List[float]] = {}

    def check_rate_limit(self, request: Request, bucket_name: str, max_requests_per_minute: int) -> None:
        if not settings.AI_API_AUTH_ENABLED:
            return

        now = time.time()
        client_host = request.client.host if request.client else "127.0.0.1"
        auth_header = request.headers.get("authorization", "") or request.headers.get("x-api-key", "")
        token_id = auth_header[-8:] if auth_header else client_host

        key = f"{bucket_name}:{token_id}"

        # Clean old timestamps outside 60-second window
        window_start = now - 60.0
        timestamps = [ts for ts in self._history.get(key, []) if ts > window_start]

        if len(timestamps) >= max_requests_per_minute:
            logger.warning(f"Rate limit triggered for '{key}' ({len(timestamps)} requests in 60s, max {max_requests_per_minute}).")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded for endpoint '{bucket_name}'. Maximum allowed is {max_requests_per_minute} requests per minute."
                },
                headers={"Retry-After": "60"}
            )

        timestamps.append(now)
        self._history[key] = timestamps


rate_limiter = RateLimiter()


async def check_chat_rate_limit(request: Request):
    rate_limiter.check_rate_limit(request, "chat", settings.CHAT_RATE_LIMIT_PER_MINUTE)


async def check_ingestion_rate_limit(request: Request):
    rate_limiter.check_rate_limit(request, "ingestion", settings.INGESTION_RATE_LIMIT_PER_MINUTE)


async def check_search_rate_limit(request: Request):
    rate_limiter.check_rate_limit(request, "search", settings.SEARCH_RATE_LIMIT_PER_MINUTE)


async def check_health_rate_limit(request: Request):
    rate_limiter.check_rate_limit(request, "health", settings.HEALTH_RATE_LIMIT_PER_MINUTE)
