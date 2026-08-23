from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import RAGService
from app.core.rate_limit import check_chat_rate_limit

router = APIRouter(tags=["Chat API"])


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/chat", response_model=ChatResponse, summary="Public Unified AI Agent Chat completion")
async def chat_endpoint(
    request: ChatRequest,
    _: None = Depends(check_chat_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Multi-tenant Unified AI Agent Chat completion endpoint (Public API)."""
    # 1. Input Validation Bounds
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
