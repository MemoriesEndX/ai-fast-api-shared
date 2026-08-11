import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status, Request
from app.core.config import settings
from app.core.security import verify_api_key, validate_tenant_auth
from app.core.rate_limit import check_ingestion_rate_limit, check_search_rate_limit
from app.utils.security_validation import (
    validate_upload_file,
    sanitize_filename,
    ALLOWED_PDF_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    ALLOWED_AUDIO_EXTENSIONS,
)
from app.schemas.knowledge import (
    KnowledgeUploadResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResultItem,
    KnowledgeDocumentStatusResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDeleteResponse,
)
from app.services.rag_service import RAGService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Management API"])


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/documents", response_model=KnowledgeUploadResponse)
async def upload_knowledge_document(
    file: UploadFile = File(..., description="Knowledge file to ingest (PDF, Video, Audio)"),
    title: str = Form(..., description="Document title"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    document_id: Optional[str] = Form(None, description="Optional unique document ID (UUID generated if empty)"),
    source_type: Optional[str] = Form(None, description="Optional source type (pdf, video, audio)"),
    content_id: Optional[str] = Form(None, description="Optional LMS content/module ID"),
    version: str = Form("1.0", description="Document version"),
    language: str = Form("id", description="Language code for transcription (id, en)"),
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Upload and ingest knowledge document (PDF, Video, Audio) into Qdrant Vector DB.
    Enforces multi-tenant isolation, file size upper bounds, MIME validation, and SHA-256 idempotency.
    """
    validate_tenant_auth(client_app, application)

    doc_id = sanitize_filename(document_id) if document_id else str(uuid.uuid4())
    file_bytes = await file.read()
    raw_filename = file.filename or "knowledge_file"

    ext = os.path.splitext(raw_filename)[1].lower()
    target_type = source_type or ("pdf" if ext == ".pdf" else ("video" if ext in ALLOWED_VIDEO_EXTENSIONS else ("audio" if ext in ALLOWED_AUDIO_EXTENSIONS else "pdf")))

    # File validation based on determined category
    if target_type == "pdf":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_PDF_EXTENSIONS, settings.MAX_PDF_SIZE_MB, category="pdf")
    elif target_type == "video":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_VIDEO_EXTENSIONS, settings.MAX_VIDEO_SIZE_MB, category="video")
    elif target_type == "audio":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_AUDIO_EXTENSIONS, settings.MAX_AUDIO_SIZE_MB, category="audio")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported source type '{target_type}'."}
        )

    result = await rag_service.ingest_knowledge(
        application=application,
        title=title,
        filename=clean_filename,
        file_bytes=file_bytes,
        document_id=doc_id,
        source_type=target_type,
        content_id=content_id,
        version=version,
        language=language,
    )
    return KnowledgeUploadResponse(**result)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request_data: KnowledgeSearchRequest,
    request: Request,
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_search_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Direct knowledge vector search strictly filtered by tenant application and optional document_id or source_type."""
    validate_tenant_auth(client_app, request_data.application)

    doc_id = sanitize_filename(request_data.document_id) if request_data.document_id else None
    top_k = min(max(1, request_data.top_k or 5), 50)

    chunks = await rag_service.search_similar_chunks(
        application=request_data.application,
        query=request_data.query,
        document_id=doc_id,
        source_type=request_data.source_type,
        top_k=top_k,
    )

    items = []
    for c in chunks:
        items.append(
            KnowledgeSearchResultItem(
                document_id=str(c.get("document_id", "")),
                title=c.get("title", ""),
                filename=c.get("filename", ""),
                source_type=c.get("source_type", "pdf"),
                score=c.get("score", 0.0),
                text=c.get("text", ""),
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                start_seconds=c.get("start_seconds"),
                end_seconds=c.get("end_seconds"),
                start_time=c.get("start_time"),
                end_time=c.get("end_time"),
                application=c.get("application", request_data.application),
            )
        )

    req_id = getattr(request.state, "request_id", None)
    return KnowledgeSearchResponse(
        query=request_data.query,
        application=request_data.application,
        results=items,
        request_id=req_id,
    )


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentStatusResponse)
async def get_knowledge_document_status(
    document_id: str,
    application: str = Query(..., description="Application tenant (owl, hr-corner)"),
    client_app: str = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Retrieve metadata and lifecycle status for a specific knowledge document."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)
    res = await rag_service.get_knowledge_document(application=application, document_id=doc_id_clean)
    return KnowledgeDocumentStatusResponse(**res)


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents(
    application: str = Query(..., description="Application tenant (owl, hr-corner)"),
    source_type: Optional[str] = Query(None, description="Optional filter by source type (pdf, video, audio)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Optional filter by status (COMPLETED, FAILED)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    client_app: str = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service),
):
    """List indexed knowledge documents for tenant application with pagination."""
    validate_tenant_auth(client_app, application)
    res = await rag_service.list_knowledge_documents(
        application=application,
        source_type=source_type,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    docs = [KnowledgeDocumentStatusResponse(**d) for d in res.get("documents", [])]
    return KnowledgeDocumentListResponse(
        application=application,
        page=res.get("page", page),
        page_size=res.get("page_size", page_size),
        total_documents=res.get("total_documents", len(docs)),
        documents=docs,
    )


@router.delete("/documents/{document_id}", response_model=KnowledgeDeleteResponse)
async def delete_knowledge_document(
    document_id: str,
    application: str = Query(..., description="Application tenant identifier (owl, hr-corner)"),
    client_app: str = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Delete knowledge document and all associated vector chunks from Qdrant."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)
    res = await rag_service.delete_document(application=application, document_id=doc_id_clean)
    return KnowledgeDeleteResponse(
        status="success" if res.get("success") else "failed",
        document_id=doc_id_clean,
        application=application,
        deleted_chunks=res.get("deleted_chunks", 0),
        message="Knowledge document and all vector points deleted successfully." if res.get("success") else "Failed to delete knowledge document."
    )


@router.post("/documents/{document_id}/reindex", response_model=KnowledgeUploadResponse)
async def reindex_knowledge_document(
    document_id: str,
    file: UploadFile = File(..., description="Updated knowledge file"),
    title: str = Form(..., description="Document title"),
    application: str = Form(..., description="Application tenant (owl, hr-corner)"),
    source_type: Optional[str] = Form(None, description="Optional source type (pdf, video, audio)"),
    content_id: Optional[str] = Form(None, description="Optional LMS content ID"),
    version: str = Form("1.1", description="Updated document version"),
    language: str = Form("id", description="Language code for transcription"),
    client_app: str = Depends(verify_api_key),
    _: None = Depends(check_ingestion_rate_limit),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Atomic reindex: processes new document first and replaces Qdrant vectors upon success."""
    validate_tenant_auth(client_app, application)
    doc_id_clean = sanitize_filename(document_id)

    file_bytes = await file.read()
    raw_filename = file.filename or "knowledge_file"
    ext = os.path.splitext(raw_filename)[1].lower()
    target_type = source_type or ("pdf" if ext == ".pdf" else ("video" if ext in ALLOWED_VIDEO_EXTENSIONS else ("audio" if ext in ALLOWED_AUDIO_EXTENSIONS else "pdf")))

    if target_type == "pdf":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_PDF_EXTENSIONS, settings.MAX_PDF_SIZE_MB, category="pdf")
    elif target_type == "video":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_VIDEO_EXTENSIONS, settings.MAX_VIDEO_SIZE_MB, category="video")
    elif target_type == "audio":
        clean_filename = validate_upload_file(raw_filename, file_bytes, ALLOWED_AUDIO_EXTENSIONS, settings.MAX_AUDIO_SIZE_MB, category="audio")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported source type '{target_type}'."}
        )

    res = await rag_service.reindex_knowledge_document(
        application=application,
        document_id=doc_id_clean,
        title=title,
        filename=clean_filename,
        file_bytes=file_bytes,
        source_type=target_type,
        content_id=content_id,
        version=version,
        language=language,
    )
    return KnowledgeUploadResponse(**res)
