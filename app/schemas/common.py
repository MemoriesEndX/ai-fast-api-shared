from typing import Dict, Optional
from pydantic import BaseModel


class RootResponse(BaseModel):
    service: str
    status: str
    version: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class LLMHealthResponse(BaseModel):
    status: str
    provider: str
    model: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    version: str
    dependencies: Dict[str, str]
