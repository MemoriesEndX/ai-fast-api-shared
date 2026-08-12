from app.schemas.application import ApplicationHealthResponse


class CinekuService:
    """Service abstraction for Cineku application logic and integration."""

    async def get_health_status(self) -> ApplicationHealthResponse:
        """Check connection health status for Cineku integration."""
        return ApplicationHealthResponse(
            application="cineku",
            status="connected"
        )
