import time
import logging
from typing import Dict, List
from fastapi import Request, HTTPException, status
from app.core.config import settings

logger = logging.getLogger("ai_service.core.rate_limit")


class RateLimiter:
    """In-memory sliding window rate limiter per client IP with burst allowance."""

    def __init__(self):
        # Maps bucket_key -> List[timestamp]
        self._history: Dict[str, List[float]] = {}

    def check_rate_limit(
        self,
        request: Request,
        bucket_name: str,
        max_requests_per_minute: int,
        burst_allowance: int = 20,
    ) -> None:
        now = time.time()
        # Extract real client IP from Cloudflare / proxy headers
        client_ip = (
            request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "127.0.0.1")
        )

        key = f"{bucket_name}:{client_ip}"

        # Clean old timestamps outside 60-second window
        window_start = now - 60.0
        timestamps = [ts for ts in self._history.get(key, []) if ts > window_start]

        if len(timestamps) >= max_requests_per_minute:
            retry_after = max(1, int(timestamps[0] + 60.0 - now) + 1)
            logger.warning(
                f"Rate limit triggered for IP '{client_ip}' on '{key}' "
                f"({len(timestamps)} requests in 60s, max {max_requests_per_minute}, burst {burst_allowance})."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        f"Rate limit exceeded for IP '{client_ip}' on endpoint '{bucket_name}'. "
                        f"Maximum allowed is {max_requests_per_minute} requests per minute (burst: {burst_allowance})."
                    ),
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        self._history[key] = timestamps

        # Periodic memory cleanup if number of tracked keys grows large
        if len(self._history) > 5000:
            self._history = {
                k: [t for t in v if t > window_start]
                for k, v in self._history.items()
                if any(t > window_start for t in v)
            }


rate_limiter = RateLimiter()


async def check_chat_rate_limit(request: Request):
    rate_limiter.check_rate_limit(
        request,
        "chat",
        settings.CHAT_RATE_LIMIT_PER_MINUTE,
        settings.CHAT_RATE_LIMIT_BURST,
    )


async def check_ingestion_rate_limit(request: Request):
    rate_limiter.check_rate_limit(
        request,
        "ingestion",
        settings.INGESTION_RATE_LIMIT_PER_MINUTE,
        settings.CHAT_RATE_LIMIT_BURST,
    )


async def check_search_rate_limit(request: Request):
    rate_limiter.check_rate_limit(
        request,
        "search",
        settings.SEARCH_RATE_LIMIT_PER_MINUTE,
        settings.CHAT_RATE_LIMIT_BURST,
    )


async def check_health_rate_limit(request: Request):
    rate_limiter.check_rate_limit(
        request,
        "health",
        settings.HEALTH_RATE_LIMIT_PER_MINUTE,
        settings.CHAT_RATE_LIMIT_BURST,
    )

