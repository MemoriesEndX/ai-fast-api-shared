from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.application import ApplicationEnum


class ChatRequest(BaseModel):
    application: Union[ApplicationEnum, str] = Field(
        ...,
        description="Originating application identifier (owl, hr-corner, etc.)",
        json_schema_extra={"example": "owl"}
    )
    user_id: Optional[Union[int, str]] = Field(
        1,
        description="ID of the user making the request",
        json_schema_extra={"example": 123}
    )
    message: str = Field(
        ...,
        description="Message prompt sent to the AI service",
        json_schema_extra={"example": "Pembelajaran apa yang cocok untuk saya?"}
    )
    document_id: Optional[Union[int, str]] = Field(
        None,
        description="Optional document ID to scope search exclusively to a specific document",
        json_schema_extra={"example": 1001}
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Optional conversation thread ID for managing chat history",
        json_schema_extra={"example": "conv_abc123"}
    )


class ChatResponse(BaseModel):
    application: str
    message: str
    answer: Optional[str] = Field(
        None,
        description="Alias for message containing the synthesized AI response"
    )
    provider: str
    model: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved citations and grounding sources (LMS, PDF, Video, Recommendation)"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation thread identifier"
    )
    tools_used: List[str] = Field(
        default_factory=list,
        description="List of MCP tools invoked during answer generation"
    )
    latency_ms: Optional[float] = Field(
        None,
        description="Total processing latency in milliseconds"
    )
    telemetry: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed latency and resource telemetry breakdown across pipeline stages"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.answer and self.message:
            self.answer = self.message
