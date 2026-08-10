from app.schemas.application import ApplicationHealthResponse


class HRCornerService:
    """Service abstraction for HR Corner application logic and integration."""

    async def get_health_status(self) -> ApplicationHealthResponse:
        """Check connection health status for HR Corner integration."""
        # Phase 1: Return placeholder connected status
        return ApplicationHealthResponse(
            application="hr-corner",
            status="connected"
        )
