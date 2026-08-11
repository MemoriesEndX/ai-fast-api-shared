from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status
from app.core.config import settings
from app.core.security import verify_api_key, validate_tenant_auth
from app.core.rate_limit import check_ingestion_rate_limit, check_search_rate_limit
from app.utils.security_validation import (
    validate_upload_file,
    sanitize_filename,
    ALLOWED_PDF_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
)
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
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Upload video file, extract audio using FFmpeg, transcribe using Whisper, and index into Vector DB."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)

    file_bytes = await file.read()
    clean_filename = validate_upload_file(
        filename=file.filename or "video.mp4",
        file_bytes=file_bytes,
        allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
        max_size_mb=settings.MAX_VIDEO_SIZE_MB,
        category="video"
    )

    res = await rag_service.ingest_video_bytes(
        application=application,
        document_id=doc_id_clean,
        title=title,
        filename=clean_filename,
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
    client_app: str = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Check processing status of video transcription job."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)
    res = await rag_service.get_video_processing_status(application=application, document_id=doc_id_clean)
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
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Reindex video by clearing old vector points and re-processing video audio transcript."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)

    file_bytes = await file.read()
    clean_filename = validate_upload_file(
        filename=file.filename or "video.mp4",
        file_bytes=file_bytes,
        allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
        max_size_mb=settings.MAX_VIDEO_SIZE_MB,
        category="video"
    )

    res = await rag_service.reindex_video_bytes(
        application=application,
        document_id=doc_id_clean,
        title=title,
        filename=clean_filename,
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
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Upload and ingest PDF document into Vector DB for RAG search with page citations."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)

    file_bytes = await file.read()
    clean_filename = validate_upload_file(
        filename=file.filename or "document.pdf",
        file_bytes=file_bytes,
        allowed_extensions=ALLOWED_PDF_EXTENSIONS,
        max_size_mb=settings.MAX_PDF_SIZE_MB,
        category="pdf"
    )

    res = await rag_service.ingest_pdf_bytes(
        application=application,
        document_id=doc_id_clean,
        title=title,
        filename=clean_filename,
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
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Reindex existing PDF document by clearing old vector points and re-ingesting PDF."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)

    file_bytes = await file.read()
    clean_filename = validate_upload_file(
        filename=file.filename or "document.pdf",
        file_bytes=file_bytes,
        allowed_extensions=ALLOWED_PDF_EXTENSIONS,
        max_size_mb=settings.MAX_PDF_SIZE_MB,
        category="pdf"
    )

    res = await rag_service.reindex_document_pdf(
        application=application,
        document_id=doc_id_clean,
        title=title,
        filename=clean_filename,
        file_bytes=file_bytes,
        content_id=content_id,
        version=version,
    )
    return PDFUploadResponse(**res)


@router.post("/documents/index", response_model=DocumentIndexResponse)
async def index_document(
    request: DocumentIndexRequest,
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Index document text into Vector DB under specified application tenant."""
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    validate_tenant_auth(client_app, app_str)
    doc_id_clean = sanitize_filename(str(request.document_id))

    res = await rag_service.index_document(
        application=app_str,
        document_id=doc_id_clean,
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
    client_app: str = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Delete document or video chunks from Vector DB by document_id and application tenant."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)
    res = await rag_service.delete_document(application=application, document_id=doc_id_clean)
    return DocumentDeleteResponse(**res)


@router.post("/search", response_model=RAGSearchResponse)
async def search_similar_documents(
    request: RAGSearchRequest,
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_search_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Search similar vector chunks filtered by tenant application and optional document_id."""
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    validate_tenant_auth(client_app, app_str)

    if request.top_k is not None and (request.top_k < 1 or request.top_k > 50):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Parameter top_k must be between 1 and 50."}
        )

    doc_id = sanitize_filename(str(request.document_id)) if request.document_id is not None else None
    results = await rag_service.search_similar_chunks(
        application=app_str,
        query=request.query,
        document_id=doc_id,
        top_k=min(max(1, request.top_k or 3), 50),
    )
    return RAGSearchResponse(
        application=app_str,
        results=results,
    )
