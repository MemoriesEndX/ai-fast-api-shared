from fastapi import APIRouter, Depends
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import RAGService

router = APIRouter(tags=["Chat API"])


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """Multi-tenant RAG-augmented AI Chat completion endpoint."""
    return await rag_service.chat_completion(request)
