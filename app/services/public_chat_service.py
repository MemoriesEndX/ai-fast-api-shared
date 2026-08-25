from app.schemas.application import ApplicationHealthResponse


class PublicChatService:
    """Service abstraction for Public Chat application logic and integration."""

    async def get_health_status(self) -> ApplicationHealthResponse:
        """Check connection health status for Public Chat integration."""
        return ApplicationHealthResponse(
            application="public-chat",
            status="connected"
        )
