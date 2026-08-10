from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Security
from app.core.security import verify_api_key
from app.schemas.rag import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    DocumentDeleteResponse,
    PDFUploadResponse,
    VideoUploadResponse,
    VideoStatusResponse,
    RAGSearchRequest,
    RAGSearchResponse,
)
from app.services.rag_service import RAGService
from app.services.authorization_service import AuthorizationService

router = APIRouter(prefix="/rag", tags=["RAG Engine"])


def get_rag_service() -> RAGService:
    return RAGService()


def get_auth_service() -> AuthorizationService:
    return AuthorizationService()


@router.post("/videos/upload", response_model=VideoUploadResponse)
async def upload_video_document(
    file: UploadFile = File(..., description="Video file to extract audio and ingest transcript"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    document_id: str = Form(..., description="Unique document ID"),
    title: str = Form(..., description="Video title"),
    content_id: Optional[str] = Form(None, description="Optional content/module ID"),
    version: str = Form("1.0", description="Video version"),
    language: str = Form("id", description="Audio language code (id, en)"),
    rag_service: RAGService = Depends(get_rag_service),
    auth_service: AuthorizationService = Depends(get_auth_service),
    client_app: str = Depends(verify_api_key),
):
    """Upload video file, extract audio using FFmpeg, transcribe using Whisper, and index into Vector DB."""
    file_bytes = await file.read()
    res = await rag_service.ingest_video_bytes(
        application=application,
        document_id=document_id,
        title=title,
        filename=file.filename or "uploaded_video.mp4",
        file_bytes=file_bytes,
        content_id=content_id,
        version=version,
        language=language,
    )
    return VideoUploadResponse(**res)


@router.get("/videos/{document_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
    document_id: str,
    application: str = Query(..., description="Application tenant (owl, hr-corner)"),
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Check processing status of video transcription job."""
    res = await rag_service.get_video_processing_status(application=application, document_id=document_id)
    return VideoStatusResponse(**res)


@router.post("/videos/{document_id}/reindex", response_model=VideoUploadResponse)
async def reindex_video_document(
    document_id: str,
    file: UploadFile = File(..., description="Updated video file"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    title: str = Form(..., description="Video title"),
    content_id: Optional[str] = Form(None, description="Optional content ID"),
    version: str = Form("1.1", description="Updated video version"),
    language: str = Form("id", description="Audio language code"),
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Reindex video by clearing old vector points and re-processing video audio transcript."""
    file_bytes = await file.read()
    res = await rag_service.reindex_video_bytes(
        application=application,
        document_id=document_id,
        title=title,
        filename=file.filename or "uploaded_video.mp4",
        file_bytes=file_bytes,
        content_id=content_id,
        version=version,
        language=language,
    )
    return VideoUploadResponse(**res)


@router.post("/documents/upload", response_model=PDFUploadResponse)
async def upload_pdf_document(
    file: UploadFile = File(..., description="PDF file to ingest"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    document_id: str = Form(..., description="Unique document ID"),
    title: str = Form(..., description="Document title"),
    content_id: Optional[str] = Form(None, description="Optional content/module ID"),
    version: str = Form("1.0", description="Document version"),
    rag_service: RAGService = Depends(get_rag_service),
    auth_service: AuthorizationService = Depends(get_auth_service),
    client_app: str = Depends(verify_api_key),
):
    """Upload and ingest PDF document into Vector DB for RAG search with page citations."""
    file_bytes = await file.read()
    res = await rag_service.ingest_pdf_bytes(
        application=application,
        document_id=document_id,
        title=title,
        filename=file.filename or "uploaded.pdf",
        file_bytes=file_bytes,
        content_id=content_id,
        version=version,
    )
    return PDFUploadResponse(**res)


@router.post("/documents/{document_id}/reindex", response_model=PDFUploadResponse)
async def reindex_pdf_document(
    document_id: str,
    file: UploadFile = File(..., description="Updated PDF file"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    title: str = Form(..., description="Document title"),
    content_id: Optional[str] = Form(None, description="Optional content ID"),
    version: str = Form("1.1", description="Updated document version"),
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Reindex existing PDF document by clearing old vector points and re-ingesting PDF."""
    file_bytes = await file.read()
    res = await rag_service.reindex_document_pdf(
        application=application,
        document_id=document_id,
        title=title,
        filename=file.filename or "uploaded.pdf",
        file_bytes=file_bytes,
        content_id=content_id,
        version=version,
    )
    return PDFUploadResponse(**res)


@router.post("/documents/index", response_model=DocumentIndexResponse)
async def index_document(
    request: DocumentIndexRequest,
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Index document text into Vector DB under specified application tenant."""
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    res = await rag_service.index_document(
        application=app_str,
        document_id=str(request.document_id),
        title=request.title,
        text=request.text,
        content_id=str(request.content_id) if request.content_id else None,
        source_type=request.source_type or "document",
    )
    return DocumentIndexResponse(**res)


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    application: str = Query(..., description="Application tenant identifier (owl, hr-corner)"),
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Delete document or video chunks from Vector DB by document_id and application tenant."""
    res = await rag_service.delete_document(application=application, document_id=document_id)
    return DocumentDeleteResponse(**res)


@router.post("/search", response_model=RAGSearchResponse)
async def search_similar_documents(
    request: RAGSearchRequest,
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Search similar vector chunks filtered by tenant application and optional document_id."""
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    doc_id = str(request.document_id) if request.document_id is not None else None
    results = await rag_service.search_similar_chunks(
        application=app_str,
        query=request.query,
        document_id=doc_id,
        top_k=request.top_k or 3,
    )
    return RAGSearchResponse(
        application=app_str,
        results=results,
    )
