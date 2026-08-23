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
    ENABLE_API_DOCS: bool = True

    OWL_BASE_URL: str = "http://owl-app.local"
    HR_CORNER_BASE_URL: str = "http://hr-corner-app.local"
    CINEKU_BASE_URL: str = "http://cineku-app.local"

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

    # File Upload & Security Size Limits
    MAX_PDF_SIZE_MB: int = 25
    MAX_VIDEO_SIZE_MB: int = 250
    MAX_AUDIO_SIZE_MB: int = 50
    MAX_VIDEO_DURATION_SECONDS: int = 3600
    WHISPER_MODEL: str = "tiny"

    # Recommendation Engine Configurable Weights (Phase 12 — 2.0 Normalized)
    RECOMMENDATION_WEIGHT_DIVISION: float = 0.20
    RECOMMENDATION_WEIGHT_ROLE: float = 0.20
    RECOMMENDATION_WEIGHT_SEMANTIC: float = 0.25
    RECOMMENDATION_WEIGHT_CLASSIFICATION: float = 0.15
    RECOMMENDATION_WEIGHT_ASSESSMENT: float = 0.10
    RECOMMENDATION_WEIGHT_PROGRESS: float = 0.10
    RECOMMENDATION_DEFAULT_LIMIT: int = 5
    RECOMMENDATION_MAX_LIMIT: int = 50


    # LMS API & MCP Configuration (Phase 7 & 8)
    LMS_API_BASE_URL: str = "http://owl-app.local"
    LMS_API_TOKEN: str = "owl-lms-secret-token"
    LMS_API_TIMEOUT: float = 10.0
    MCP_ENABLED: bool = True
    MCP_MAX_TOOL_CALLS: int = 5
    TOOL_TIMEOUT: float = 15.0

    # Phase 8 Agent & Conversation Settings
    CHAT_MAX_HISTORY: int = 5
    CHAT_MAX_TOOL_CALLS: int = 5
    RAG_MAX_CONTEXT_CHARS: int = 2000
    ALLOWED_TOOLS: List[str] = [
        "get_user_learning_profile",
        "get_learning_progress",
        "get_user_assessments",
        "search_learning_content",
        "search_learning_playlist",
        "get_content_detail",
        "get_playlist_detail",
        "get_learning_recommendations",
        "search_pdf_knowledge",
        "search_video_transcript",
    ]

    # Phase 9 REST API Hardening & Security Configuration (Step 33 Public API Mode)
    AI_API_AUTH_ENABLED: bool = False
    AI_API_KEY: str = "dev-shared-ai-key-change-in-production"
    OWL_AI_API_KEY: str = "owl-secret-api-key"
    HR_AI_API_KEY: str = "hr-corner-secret-api-key"
    CINEKU_AI_API_KEY: str = "cineku-secret-api-key"

    CHAT_RATE_LIMIT_PER_MINUTE: int = 100
    CHAT_RATE_LIMIT_BURST: int = 20
    INGESTION_RATE_LIMIT_PER_MINUTE: int = 100
    SEARCH_RATE_LIMIT_PER_MINUTE: int = 100
    HEALTH_RATE_LIMIT_PER_MINUTE: int = 300
    MAX_RETRIES: int = 2

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

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV.lower() in ("production", "prod")


settings = Settings()

