from fastapi import APIRouter, Depends
from app.schemas.application import ApplicationHealthResponse
from app.services.owl_service import OWLService

router = APIRouter(prefix="/owl", tags=["OWL Application Foundation"])


def get_owl_service() -> OWLService:
    return OWLService()


@router.get("/health", response_model=ApplicationHealthResponse)
async def owl_health_check(service: OWLService = Depends(get_owl_service)):
    """OWL Application integration health endpoint."""
    return await service.get_health_status()
