from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.application import ApplicationEnum


class ChatRequest(BaseModel):
    application: Union[ApplicationEnum, str] = Field(
        ...,
        description="Originating application identifier (owl, hr-corner, etc.)",
        json_schema_extra={"example": "owl"}
    )
    user_id: Union[int, str] = Field(
        ...,
        description="ID of the user making the request",
        json_schema_extra={"example": 123}
    )
    message: str = Field(
        ...,
        description="Message prompt sent to the AI service",
        json_schema_extra={"example": "Apa APD yang wajib digunakan?"}
    )
    document_id: Optional[Union[int, str]] = Field(
        None,
        description="Optional document ID to scope search exclusively to a specific document",
        json_schema_extra={"example": 1001}
    )


class ChatResponse(BaseModel):
    application: str
    message: str
    provider: str
    model: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved source PDF chunk citations with page numbers"
    )
