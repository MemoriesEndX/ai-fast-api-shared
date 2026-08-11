import httpx
from typing import Optional, Dict, Any
from app.core.config import settings


class HRCornerClient:
    """HTTP Client for interacting with HR Corner REST API."""

    def __init__(self, base_url: str = settings.HR_CORNER_BASE_URL, api_key: Optional[str] = settings.HR_AI_API_KEY):
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Shared-AI-Service/1.0",
            "Accept": "application/json",
        }
        if api_key:
            self.headers["X-AI-Service-Key"] = api_key

    async def ping_hr_corner(self) -> bool:
        """Ping HR Corner health endpoint (Placeholder for future phases)."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/health", headers=self.headers)
                return res.status_code == 200
        except Exception:
            # Fallback for Phase 1 where HR Corner application might not be reachable yet
            return True
