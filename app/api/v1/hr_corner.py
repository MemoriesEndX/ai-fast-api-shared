from fastapi import APIRouter, Depends
from app.schemas.application import ApplicationHealthResponse
from app.services.hr_corner_service import HRCornerService

router = APIRouter(prefix="/hr-corner", tags=["HR Corner Application Foundation"])


def get_hr_corner_service() -> HRCornerService:
    return HRCornerService()


@router.get("/health", response_model=ApplicationHealthResponse)
async def hr_corner_health_check(service: HRCornerService = Depends(get_hr_corner_service)):
    """HR Corner Application integration health endpoint."""
    return await service.get_health_status()
