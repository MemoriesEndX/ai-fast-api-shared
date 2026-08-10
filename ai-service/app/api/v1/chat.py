from fastapi import APIRouter, Depends
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import BaseLLMService, get_llm_service

router = APIRouter(tags=["Chat API"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    llm_service: BaseLLMService = Depends(get_llm_service),
):
    """Chat endpoint supporting multi-tenant client routing (OWL, HR Corner, etc.)."""
    return await llm_service.generate_response(request)
