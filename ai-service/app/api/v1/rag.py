from fastapi import APIRouter, Depends, Query, Security
from app.core.security import verify_api_key
from app.schemas.rag import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    DocumentDeleteResponse,
    RAGSearchRequest,
    RAGSearchResponse,
)
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["RAG Engine"])


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/documents/index", response_model=DocumentIndexResponse)
async def index_document(
    request: DocumentIndexRequest,
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Index document text into Vector DB under the specified application tenant."""
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
    """Delete document chunks from Vector DB by document_id and application tenant."""
    res = await rag_service.delete_document(application=application, document_id=document_id)
    return DocumentDeleteResponse(**res)


@router.post("/search", response_model=RAGSearchResponse)
async def search_similar_documents(
    request: RAGSearchRequest,
    rag_service: RAGService = Depends(get_rag_service),
    client_app: str = Depends(verify_api_key),
):
    """Search similar vector chunks filtered by tenant application."""
    app_str = str(request.application.value if hasattr(request.application, 'value') else request.application)
    results = await rag_service.search_similar_chunks(
        application=app_str,
        query=request.query,
        top_k=request.top_k or 3,
    )
    return RAGSearchResponse(
        application=app_str,
        results=results,
    )
