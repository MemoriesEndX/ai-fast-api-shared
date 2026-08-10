from fastapi import APIRouter, Depends
from app.core.config import settings
from app.schemas.common import HealthResponse, LLMHealthResponse
from app.services.llm_service import BaseLLMService, get_llm_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def api_health_check():
    """Health check endpoint under API v1 prefix."""
    return HealthResponse(
        status="ok",
        service="ai-service",
        version=settings.APP_VERSION,
    )


@router.get("/health/llm", response_model=LLMHealthResponse)
async def llm_health_check(llm_service: BaseLLMService = Depends(get_llm_service)):
    """Health check endpoint for LLM inference backend (llama-server)."""
    health_info = await llm_service.check_health()
    return LLMHealthResponse(**health_info)
