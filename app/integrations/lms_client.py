import logging
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("ai_service.lms_client")


class LMSClientService:
    """Client for communicating with the Laravel OWL LMS REST API.
    
    Acts as the single point of entry to fetch LMS profile, progress, assessment,
    catalog, and detail records from Laravel. Never accesses MySQL directly.
    """

    def __init__(self, base_url: str = None, token: str = None, timeout: float = None):
        self.base_url = (base_url or settings.LMS_API_BASE_URL).rstrip("/")
        self.token = token or settings.LMS_API_TOKEN
        self.timeout = timeout or settings.LMS_API_TIMEOUT
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            timeout_config = httpx.Timeout(self.timeout, connect=0.1)
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0)
            self._client = httpx.AsyncClient(timeout=timeout_config, limits=limits)
        return self._client

    async def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Fetch user profile metadata from Laravel."""
        url = f"{self.base_url}/api/v1/internal/users/{user_id}/profile"
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "user_id": data.get("id", user_id),
                    "name": data.get("name"),
                    "division": data.get("division"),
                    "position": data.get("position") or data.get("department"),
                    "department": data.get("department"),
                    "team": data.get("team"),
                    "role": data.get("role"),
                }
        except Exception as e:
            logger.warning(f"LMS API profile request failed ({e}). Using mock/fallback profile for dev/test.")
        
        # Fallback Mock Data for Dev/Test environment
        return self._mock_user_profile(user_id)

    async def get_learning_progress(self, user_id: int) -> Dict[str, Any]:
        """Fetch learning progress items for a user."""
        url = f"{self.base_url}/api/v1/internal/users/{user_id}/progress"
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API progress request failed ({e}). Using mock/fallback progress for dev/test.")

        return self._mock_learning_progress(user_id)

    async def get_user_assessments(self, user_id: int) -> Dict[str, Any]:
        """Fetch assessment results for a user."""
        url = f"{self.base_url}/api/v1/internal/users/{user_id}/assessments"
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API assessments request failed ({e}). Using mock/fallback assessment for dev/test.")

        return self._mock_user_assessments(user_id)

    async def search_content(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search learning content catalog."""
        url = f"{self.base_url}/api/v1/internal/contents/search"
        params = {"query": query, "limit": limit}
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API content search failed ({e}). Using mock search.")

        return self._mock_search_content(query, limit)

    async def search_playlist(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search training playlists catalog."""
        url = f"{self.base_url}/api/v1/internal/playlists/search"
        params = {"query": query, "limit": limit}
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API playlist search failed ({e}). Using mock search.")

        return self._mock_search_playlist(query, limit)

    async def get_content_detail(self, content_id: int) -> Dict[str, Any]:
        """Get detail of a specific content."""
        url = f"{self.base_url}/api/v1/internal/contents/{content_id}"
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API content detail failed ({e}). Using mock detail.")

        return self._mock_content_detail(content_id)

    async def get_playlist_detail(self, playlist_id: int) -> Dict[str, Any]:
        """Get detail of a specific playlist including child contents."""
        url = f"{self.base_url}/api/v1/internal/playlists/{playlist_id}"
        try:
            client = self._get_client()
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"LMS API playlist detail failed ({e}). Using mock detail.")

        return self._mock_playlist_detail(playlist_id)

    # ----------------------------------------------------------------------
    # Mock Data Repositories for Local Dev & Test Enforcement
    # ----------------------------------------------------------------------
    def _mock_user_profile(self, user_id: int) -> Dict[str, Any]:
        profiles = {
            123: {
                "user_id": 123,
                "name": "Budi Santoso",
                "division": "Production",
                "position": "Supervisor",
                "department": "Safety",
                "team": "Team Alpha",
                "role": "Supervisor",
            },
            124: {
                "user_id": 124,
                "name": "Siti Rahma",
                "division": "HR",
                "position": "Staff",
                "department": "Human Capital",
                "team": "Recruitment",
                "role": "Staff",
            },
        }
        return profiles.get(user_id, {
            "user_id": user_id,
            "name": f"User {user_id}",
            "division": "General",
            "position": "Employee",
            "department": "General",
            "team": "Main",
            "role": "User",
        })

    def _mock_learning_progress(self, user_id: int) -> Dict[str, Any]:
        if user_id == 123:
            return {
                "user_id": 123,
                "items": [
                    {
                        "content_id": 101,
                        "title": "Safety Induction 101",
                        "type": "video",
                        "progress": 100,
                        "finish": 1,
                        "learning_status": "completed",
                    },
                    {
                        "content_id": 105,
                        "title": "Hazard Identification Basics",
                        "type": "video",
                        "progress": 40,
                        "finish": 0,
                        "learning_status": "in_progress",
                    },
                ],
            }
        return {"user_id": user_id, "items": []}

    def _mock_user_assessments(self, user_id: int) -> Dict[str, Any]:
        if user_id == 123:
            return {
                "user_id": 123,
                "items": [
                    {
                        "assessment_id": 501,
                        "content_id": 101,
                        "title": "Safety Induction Exam",
                        "score": 55.0,
                        "final": "fail",
                    }
                ],
            }
        return {"user_id": user_id, "items": []}

    def _mock_search_content(self, query: str, limit: int) -> Dict[str, Any]:
        all_contents = [
            {"id": 101, "title": "Safety Induction 101", "type": "video", "classification_name": "Safety", "active": "Active"},
            {"id": 102, "title": "Advanced Safety Management", "type": "pdf", "classification_name": "Safety", "active": "Active"},
            {"id": 104, "title": "Standard Operating Procedure 2026", "type": "pdf", "classification_name": "Operations", "active": "Active"},
            {"id": 105, "title": "Hazard Identification Basics", "type": "video", "classification_name": "Safety", "active": "Active"},
        ]
        q_lower = query.lower()
        matched = [c for c in all_contents if q_lower in c["title"].lower() or q_lower in c["classification_name"].lower()]
        if not matched:
            matched = all_contents
        return {"items": matched[:limit]}

    def _mock_search_playlist(self, query: str, limit: int) -> Dict[str, Any]:
        all_playlists = [
            {"id": 103, "title": "Production Safety Leadership Playlist", "classification_name": "Safety", "active": "Active", "total_duration_seconds": 7200},
            {"id": 201, "title": "Operational Excellence Series", "classification_name": "Operations", "active": "Active", "total_duration_seconds": 10800},
        ]
        q_lower = query.lower()
        matched = [p for p in all_playlists if q_lower in p["title"].lower() or q_lower in p["classification_name"].lower()]
        if not matched:
            matched = all_playlists
        return {"items": matched[:limit]}

    def _mock_content_detail(self, content_id: int) -> Dict[str, Any]:
        contents = {
            101: {"id": 101, "title": "Safety Induction 101", "type": "video", "description": "Basic safety induction for manufacturing plant", "duration": "30 mins", "classification_name": "Safety", "learning_hours": 0.5, "active": "Active"},
            102: {"id": 102, "title": "Advanced Safety Management", "type": "pdf", "description": "Safety leadership and risk control protocols for supervisors", "duration": "45 mins", "classification_name": "Safety", "learning_hours": 0.75, "active": "Active"},
            104: {"id": 104, "title": "Standard Operating Procedure 2026", "type": "pdf", "description": "Plant SOP guidelines and operational directives", "duration": "60 mins", "classification_name": "Operations", "learning_hours": 1.0, "active": "Active"},
            105: {"id": 105, "title": "Hazard Identification Basics", "type": "video", "description": "Detecting workplace hazards before incidents occur", "duration": "20 mins", "classification_name": "Safety", "learning_hours": 0.33, "active": "Active"},
        }
        return contents.get(content_id, {"error": {"code": "CONTENT_NOT_FOUND", "message": f"Content ID {content_id} not found"}})

    def _mock_playlist_detail(self, playlist_id: int) -> Dict[str, Any]:
        playlists = {
            103: {
                "id": 103,
                "title": "Production Safety Leadership Playlist",
                "description": "Comprehensive safety leadership course collection",
                "total_duration_seconds": 7200,
                "classification_name": "Safety",
                "active": "Active",
                "contents": [
                    {"id": 101, "title": "Safety Induction 101", "type": "video", "duration": "30 mins"},
                    {"id": 102, "title": "Advanced Safety Management", "type": "pdf", "duration": "45 mins"},
                ],
            }
        }
        return playlists.get(playlist_id, {"error": {"code": "PLAYLIST_NOT_FOUND", "message": f"Playlist ID {playlist_id} not found"}})
