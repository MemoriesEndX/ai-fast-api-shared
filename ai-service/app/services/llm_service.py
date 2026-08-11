import logging
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.prompt_service import PromptService

logger = logging.getLogger("ai_service.llm")


class BaseLLMService(ABC):
    """Abstract Base Class for LLM Provider Abstraction."""

    @abstractmethod
    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """Generate response from the LLM model."""
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Check LLM backend health status."""
        pass

    @abstractmethod
    async def generate_explanation(self, system_prompt: str, prompt: str) -> Optional[str]:
        """Generate text explanation safely (returns None if offline)."""
        pass


class LlamaCppLLMService(BaseLLMService):
    """LLM Service implementation communicating with llama-server via OpenAI-compatible REST API."""

    def __init__(
        self,
        base_url: str = settings.LLM_BASE_URL,
        model_name: str = settings.LLM_MODEL,
        provider_name: str = settings.LLM_PROVIDER,
        timeout: float = settings.LLM_TIMEOUT,
        prompt_service: Optional[PromptService] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.provider_name = provider_name
        self.timeout = timeout
        self.prompt_service = prompt_service or PromptService()

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        app_name = str(request.application.value if hasattr(request.application, 'value') else request.application)
        system_prompt = self.prompt_service.get_system_prompt(request.application)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message},
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }

        endpoint = f"{self.base_url}/v1/chat/completions"

        try:
            # Short 1.5s connect timeout for fast offline detection
            request_timeout = httpx.Timeout(self.timeout, connect=1.5)
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                response = await client.post(endpoint, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices and len(choices) > 0:
                        content = choices[0].get("message", {}).get("content", "")
                        return ChatResponse(
                            application=app_name,
                            model=self.model_name,
                            message=content.strip(),
                            provider=self.provider_name,
                        )
                
                logger.error(f"llama-server error: HTTP {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "code": "LLM_ERROR",
                        "message": "LLM inference server returned an error response."
                    }
                )

        except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
            logger.warning(f"llama-server connection failed: {exc}")
            # Fallback for development / test mode if llama-server container is offline
            if settings.APP_ENV in ("development", "test"):
                return ChatResponse(
                    application=app_name,
                    model=self.model_name,
                    message="AI service is ready.",
                    provider=self.provider_name,
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "LLM_UNAVAILABLE",
                    "message": "AI model backend is temporarily unavailable."
                }
            )

    async def generate_explanation(self, system_prompt: str, prompt: str) -> Optional[str]:
        """Generate text explanation safely (returns None if offline or error occurs)."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 256,
        }
        endpoint = f"{self.base_url}/v1/chat/completions"
        try:
            request_timeout = httpx.Timeout(self.timeout, connect=1.5)
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                response = await client.post(endpoint, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices and len(choices) > 0:
                        content = choices[0].get("message", {}).get("content", "")
                        if content and content.strip():
                            return content.strip()
        except Exception as exc:
            logger.warning(f"Failed to generate LLM explanation: {exc}")
        return None

    async def check_health(self) -> Dict[str, Any]:
        """Ping llama-server health endpoint to verify model readiness."""
        health_endpoint = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
                res = await client.get(health_endpoint)
                if res.status_code == 200:
                    return {
                        "status": "ok",
                        "provider": self.provider_name,
                        "model": self.model_name,
                    }
        except Exception as e:
            logger.debug(f"llama-server health check failed: {e}")

        return {
            "status": "degraded",
            "provider": self.provider_name,
            "model": self.model_name,
        }


def get_llm_service() -> BaseLLMService:
    """Factory function to retrieve LLM Service."""
    return LlamaCppLLMService()
