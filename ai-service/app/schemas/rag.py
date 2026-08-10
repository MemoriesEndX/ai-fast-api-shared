from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from app.schemas.application import ApplicationEnum


class DocumentIndexRequest(BaseModel):
    application: Union[ApplicationEnum, str] = Field(..., description="Application tenant (owl, hr-corner)")
    document_id: Union[int, str] = Field(..., description="Unique document ID")
    content_id: Optional[Union[int, str]] = Field(None, description="Optional content/module ID")
    title: str = Field(..., description="Document title")
    text: str = Field(..., description="Full text content of document")
    source_type: Optional[str] = Field("document", description="Document type (pdf, article, video)")


class PDFUploadResponse(BaseModel):
    status: str
    application: str
    document_id: str
    filename: str
    document_hash: str
    pages: int
    chunks: int


class VideoUploadResponse(BaseModel):
    status: str
    application: str
    document_id: str
    filename: str
    document_hash: str
    duration_seconds: float
    segments: int
    chunks: int


class VideoStatusResponse(BaseModel):
    document_id: str
    application: str
    status: str
    progress: int


class DocumentIndexResponse(BaseModel):
    status: str
    application: str
    document_id: str
    chunks: int


class DocumentDeleteResponse(BaseModel):
    status: str
    application: str
    document_id: str


class RAGSearchRequest(BaseModel):
    application: Union[ApplicationEnum, str] = Field(..., description="Application tenant filter")
    query: str = Field(..., description="Search query string")
    document_id: Optional[Union[int, str]] = Field(None, description="Optional document ID filter")
    top_k: Optional[int] = Field(3, description="Number of top chunks to return")


class ChunkSearchResult(BaseModel):
    document_id: str
    content_id: Optional[str] = None
    source_type: Optional[str] = "pdf"
    title: str
    filename: Optional[str] = None
    chunk_index: int
    page_start: Optional[int] = 1
    page_end: Optional[int] = 1
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    score: float
    text: str
    application: str


class RAGSearchResponse(BaseModel):
    application: str
    results: List[ChunkSearchResult]
