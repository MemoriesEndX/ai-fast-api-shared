from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse


class BaseLLMService(ABC):
    """Abstract Base Class for LLM Provider Abstraction."""

    @abstractmethod
    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """Generate response from the LLM model."""
        pass


class LlamaCppLLMService(BaseLLMService):
    """LLM Service implementation targeting llama.cpp / OpenAI-compatible endpoint."""

    def __init__(self, base_url: str = settings.LLM_BASE_URL, provider_name: str = settings.LLM_PROVIDER):
        self.base_url = base_url
        self.provider_name = provider_name
        self.model_name: Optional[str] = None

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        # Phase 1 Placeholder implementation:
        # Returns ready status without connecting to Qwen / llama-server yet.
        # Phase 2 will plug in HTTP calls to llama-server via self.base_url seamlessly.
        app_name = str(request.application.value if hasattr(request.application, 'value') else request.application)
        
        return ChatResponse(
            application=app_name,
            message="AI service is ready.",
            provider=self.provider_name,
            model=self.model_name,
        )


def get_llm_service() -> BaseLLMService:
    """Factory function to get configured LLM service provider."""
    if settings.LLM_PROVIDER == "llama_cpp":
        return LlamaCppLLMService(base_url=settings.LLM_BASE_URL)
    # Default fallback
    return LlamaCppLLMService(base_url=settings.LLM_BASE_URL)
