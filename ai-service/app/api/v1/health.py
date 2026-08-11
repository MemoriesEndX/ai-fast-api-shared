from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import settings
from app.schemas.common import HealthResponse, LLMHealthResponse, ReadinessResponse
from app.services.llm_service import BaseLLMService, get_llm_service
from app.services.qdrant_service import qdrant_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def api_health_check():
    """Liveness check endpoint under API v1 prefix."""
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


@router.get("/health/readiness", response_model=ReadinessResponse)
async def readiness_check(llm_service: BaseLLMService = Depends(get_llm_service)):
    """Readiness probe checking dependency readiness (Qdrant & llama-server)."""
    deps: Dict[str, str] = {}
    is_ready = True

    try:
        llm_status = await llm_service.check_health()
        deps["llm"] = llm_status.get("status", "ok")
    except Exception:
        deps["llm"] = "unavailable"
        is_ready = False

    try:
        qdrant_ok = await qdrant_service.health_check()
        deps["qdrant"] = "ok" if qdrant_ok else "memory_fallback"
    except Exception:
        deps["qdrant"] = "unavailable"

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AI_SERVICE_UNAVAILABLE",
                "message": "Service is not ready to handle workloads.",
                "dependencies": deps,
            }
        )

    return ReadinessResponse(
        status="ready",
        service="ai-service",
        version=settings.APP_VERSION,
        dependencies=deps,
    )
