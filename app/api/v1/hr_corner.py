from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.application import ApplicationEnum, ApplicationHealthResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.hr_corner_service import HRCornerService
from app.services.rag_service import RAGService
from app.core.security import verify_api_key, validate_tenant_auth
from app.core.rate_limit import check_chat_rate_limit

router = APIRouter(prefix="/hr-corner", tags=["HR Corner Application Foundation"])


def get_hr_corner_service() -> HRCornerService:
    return HRCornerService()


def get_rag_service() -> RAGService:
    return RAGService()


@router.get("/health", response_model=ApplicationHealthResponse)
async def hr_corner_health_check(service: HRCornerService = Depends(get_hr_corner_service)):
    """HR Corner Application integration health endpoint."""
    return await service.get_health_status()


@router.post("/chat", response_model=ChatResponse)
async def hr_corner_chat_endpoint(
    request: ChatRequest,
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_chat_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """HR Corner Application dedicated Chat completion endpoint."""
    request.application = ApplicationEnum.HR_CORNER

    # 1. Tenant Authorization Check
    validate_tenant_auth(client_app, "hr-corner")

    # 2. Input Validation Bounds
    if len(request.message.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Message content cannot be empty."}
        )
    if len(request.message) > 4000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Message payload exceeds maximum limit of 4000 characters."}
        )

    return await rag_service.chat_completion(request)
