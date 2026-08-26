import logging
import time
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
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

    @abstractmethod
    async def generate_completion(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
        max_tokens: int = 256,
    ) -> Optional[str]:
        """Generate chat completion from LLM backend."""
        pass

    async def generate_completion_detailed(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
        max_tokens: int = 256,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Generate chat completion with fine-grained execution telemetry."""
        res = await self.generate_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return res, {}


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
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            timeout_config = httpx.Timeout(self.timeout, connect=0.5)
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0)
            self._client = httpx.AsyncClient(timeout=timeout_config, limits=limits)
        return self._client

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
        start_time = time.time()
        from app.core.metrics import metrics_registry
        metrics_registry.inc("llm_requests_total", labels={"model": self.model_name, "provider": self.provider_name})

        try:
            client = self._get_client()
            response = await client.post(endpoint, json=payload)
            duration = time.time() - start_time
            metrics_registry.observe("llm_latency_seconds", duration, labels={"model": self.model_name})
            
            if response.status_code == 200:
                data = response.json()
                usage = data.get("usage", {})
                if usage and isinstance(usage, dict):
                    total_tokens = usage.get("total_tokens", 0)
                    if total_tokens > 0:
                        metrics_registry.inc("llm_tokens_total", value=float(total_tokens), labels={"model": self.model_name})

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
            duration = time.time() - start_time
            metrics_registry.observe("llm_latency_seconds", duration, labels={"model": self.model_name})
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
            client = self._get_client()
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

    async def generate_completion_detailed(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
        max_tokens: int = 256,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Generate chat completion from LLM backend with detailed telemetry metrics."""
        final_messages = []
        if messages:
            final_messages = list(messages)
        else:
            if system_prompt:
                final_messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                final_messages.append({"role": "user", "content": user_prompt})
            elif prompt:
                final_messages.append({"role": "user", "content": prompt})

        if not final_messages:
            return None, {}

        payload = {
            "model": self.model_name,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        endpoint = f"{self.base_url}/v1/chat/completions"
        t0 = time.perf_counter()
        telemetry: Dict[str, Any] = {"max_tokens": max_tokens}

        try:
            client = self._get_client()
            response = await client.post(endpoint, json=payload)
            llm_duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["llm_latency_ms"] = llm_duration_ms

            if response.status_code == 200:
                data = response.json()
                usage = data.get("usage", {})
                if usage and isinstance(usage, dict):
                    telemetry["prompt_tokens"] = usage.get("prompt_tokens", 0)
                    telemetry["completion_tokens"] = usage.get("completion_tokens", 0)
                    telemetry["total_tokens"] = usage.get("total_tokens", 0)

                timings = data.get("timings", {})
                if timings and isinstance(timings, dict):
                    telemetry["prompt_eval_ms"] = round(timings.get("prompt_eval_duration_ms", 0), 2)
                    telemetry["generation_ms"] = round(timings.get("predicted_duration_ms", 0), 2)

                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content", "")
                    if content and content.strip():
                        return content.strip(), telemetry
            logger.warning(f"llama-server returned HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:
            telemetry["llm_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["error"] = str(exc)
            logger.warning(f"Failed to generate LLM completion: {exc}")

        return None, telemetry

    async def generate_completion(
        self,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
        max_tokens: int = 256,
    ) -> Optional[str]:
        """Generate chat completion from LLM backend."""
        content, _ = await self.generate_completion_detailed(
            prompt=prompt,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return content

    async def check_health(self) -> Dict[str, Any]:
        """Ping llama-server health endpoint to verify model readiness."""
        health_endpoint = f"{self.base_url}/health"
        try:
            client = self._get_client()
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
