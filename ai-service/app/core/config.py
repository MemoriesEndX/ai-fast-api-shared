import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Shared AI Service"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"

    API_PREFIX: str = "/api/v1"

    OWL_BASE_URL: str = "http://owl-app.local"
    HR_CORNER_BASE_URL: str = "http://hr-corner-app.local"

    # LLM Settings
    LLM_PROVIDER: str = "llama_cpp"
    LLM_BASE_URL: str = "http://llama-server:8080"
    LLM_MODEL: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LLM_TIMEOUT: float = 120.0
    LLM_MAX_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.2

    # Qdrant Vector DB Settings
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION_PREFIX: str = "shared_ai"

    # Embedding & RAG Settings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 3
    RAG_SCORE_THRESHOLD: float = 0.4

    # Security Keys
    AI_API_KEY: str = "dev-shared-ai-key-change-in-production"
    OWL_AI_API_KEY: str = "owl-secret-api-key"
    HR_AI_API_KEY: str = "hr-corner-secret-api-key"

    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
