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

    LLM_PROVIDER: str = "llama_cpp"
    LLM_BASE_URL: str = "http://llama-server:8080"

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
