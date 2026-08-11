from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class KnowledgeUploadResponse(BaseModel):
    """Structured response for knowledge file upload ingestion."""
    status: str = Field(..., description="Ingestion status (completed, duplicate, failed, processing)")
    document_id: str = Field(..., description="Unique document ID (UUID)")
    document_hash: str = Field(..., description="SHA-256 fingerprint hash of file contents")
    title: str = Field(..., description="Document title")
    filename: str = Field(..., description="Sanitized original filename")
    source_type: str = Field(..., description="Source type (pdf, video, audio)")
    application: str = Field(..., description="Tenant application (owl, hr-corner)")
    chunks_indexed: int = Field(0, description="Total vector chunks indexed into Qdrant")
    message: str = Field(..., description="Human readable status message")


class KnowledgeSearchRequest(BaseModel):
    """Structured request for direct Knowledge Vector Search."""
    application: str = Field(..., description="Application tenant identifier (owl, hr-corner)")
    query: str = Field(..., min_length=1, description="Natural language search query")
    source_type: Optional[str] = Field(None, description="Optional filter by source type (pdf, video, audio)")
    document_id: Optional[str] = Field(None, description="Optional filter by specific document_id")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="Maximum number of vector results (1-50)")


class KnowledgeSearchResultItem(BaseModel):
    """Knowledge search result item schema."""
    document_id: str
    title: str
    filename: str
    source_type: str
    score: float
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    application: str


class KnowledgeSearchResponse(BaseModel):
    """Structured response for Knowledge Vector Search."""
    query: str
    application: str
    results: List[KnowledgeSearchResultItem]
    request_id: Optional[str] = None


class KnowledgeDocumentStatusResponse(BaseModel):
    """Document status and metadata response schema."""
    document_id: str
    application: str
    title: str
    filename: str
    source_type: str
    status: str = Field("COMPLETED", description="Lifecycle status (PENDING, PROCESSING, COMPLETED, FAILED)")
    document_hash: Optional[str] = None
    chunks_count: int = 0
    created_at: Optional[str] = None


class KnowledgeDocumentListResponse(BaseModel):
    """Paginated list of knowledge documents response schema."""
    application: str
    page: int
    page_size: int
    total_documents: int
    documents: List[KnowledgeDocumentStatusResponse]


class KnowledgeDeleteResponse(BaseModel):
    """Response schema for knowledge document deletion."""
    status: str
    document_id: str
    application: str
    deleted_chunks: int
    message: str
