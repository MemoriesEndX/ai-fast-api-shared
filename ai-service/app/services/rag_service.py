import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.rag_prompt_service import RAGPromptService
from app.services.pdf_service import PDFService
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger("ai_service.rag")


class RAGService:
    """Orchestrator for PDF & Document Ingestion, Vector Search, and RAG Chat completions."""

    def __init__(
        self,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        qdrant_service: Optional[QdrantService] = None,
        rag_prompt_service: Optional[RAGPromptService] = None,
        pdf_service: Optional[PDFService] = None,
        llm_service: Optional[BaseLLMService] = None,
    ):
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()
        self.rag_prompt_service = rag_prompt_service or RAGPromptService()
        self.pdf_service = pdf_service or PDFService()
        self.llm_service = llm_service or get_llm_service()

    async def ingest_pdf_bytes(
        self,
        application: str,
        document_id: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        content_id: Optional[str] = None,
        version: str = "1.0",
    ) -> Dict[str, Any]:
        """Validate, extract, chunk, embed, and index a PDF document into Qdrant."""
        # 1. Validate PDF file
        self.pdf_service.validate_pdf_file(filename, file_bytes)

        # 2. Extract page-structured text and document hash
        pages_data, doc_hash, total_pages = self.pdf_service.extract_structured_text(file_bytes)

        # 3. Check for existing document hash idempotency
        existing = await self.qdrant_service.get_document_by_hash(application, doc_hash)
        if existing and existing.get("document_id") == str(document_id):
            logger.info(f"PDF document {filename} with hash {doc_hash[:8]} already indexed. Skipping duplicate.")
            return {
                "status": "already_indexed",
                "application": application,
                "document_id": document_id,
                "filename": filename,
                "document_hash": doc_hash,
                "pages": total_pages,
                "chunks": 0,
            }

        # 4. Page-aware chunking
        chunks = self.chunking_service.chunk_pages(pages_data)
        if not chunks:
            return {
                "status": "error",
                "application": application,
                "document_id": document_id,
                "chunks": 0,
                "message": "No text chunks generated from PDF."
            }

        # 5. Generate vector embeddings
        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_service.embed_batch(texts)

        # 6. Assemble chunk payloads
        chunks_data = []
        for c, emb in zip(chunks, embeddings):
            chunks_data.append({
                "application": application,
                "document_id": str(document_id),
                "content_id": str(content_id) if content_id else None,
                "source_type": "pdf",
                "title": title,
                "filename": filename,
                "document_hash": doc_hash,
                "version": version,
                "chunk_index": c["chunk_index"],
                "page_start": c.get("page_start", 1),
                "page_end": c.get("page_end", 1),
                "text": c["text"],
                "vector": emb,
            })

        # 7. Upsert to Qdrant Vector DB
        success = await self.qdrant_service.upsert_chunks(chunks_data)

        return {
            "status": "indexed" if success else "failed",
            "application": application,
            "document_id": document_id,
            "filename": filename,
            "document_hash": doc_hash,
            "pages": total_pages,
            "chunks": len(chunks),
        }

    async def index_document(
        self,
        application: str,
        document_id: str,
        title: str,
        text: str,
        content_id: Optional[str] = None,
        source_type: str = "document",
    ) -> Dict[str, Any]:
        """Index flat document text (Legacy or direct text payload)."""
        pages_data = [{"page": 1, "text": text}]
        chunks = self.chunking_service.chunk_pages(pages_data)

        if not chunks:
            return {
                "status": "error",
                "application": application,
                "document_id": document_id,
                "chunks": 0,
                "message": "Empty document text provided."
            }

        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_service.embed_batch(texts)

        chunks_data = []
        for c, emb in zip(chunks, embeddings):
            chunks_data.append({
                "application": application,
                "document_id": str(document_id),
                "content_id": str(content_id) if content_id else None,
                "source_type": source_type,
                "title": title,
                "chunk_index": c["chunk_index"],
                "page_start": 1,
                "page_end": 1,
                "text": c["text"],
                "vector": emb,
            })

        success = await self.qdrant_service.upsert_chunks(chunks_data)

        return {
            "status": "indexed" if success else "failed",
            "application": application,
            "document_id": document_id,
            "chunks": len(chunks),
        }

    async def delete_document(self, application: str, document_id: str) -> Dict[str, Any]:
        """Delete all document vector points under application tenant."""
        success = await self.qdrant_service.delete_document(application, document_id)
        return {
            "status": "deleted" if success else "failed",
            "application": application,
            "document_id": document_id,
        }

    async def reindex_document_pdf(
        self,
        application: str,
        document_id: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        content_id: Optional[str] = None,
        version: str = "1.0",
    ) -> Dict[str, Any]:
        """Reindex document by first clearing existing vectors, then re-ingesting PDF."""
        await self.delete_document(application, document_id)
        return await self.ingest_pdf_bytes(
            application=application,
            document_id=document_id,
            title=title,
            filename=filename,
            file_bytes=file_bytes,
            content_id=content_id,
            version=version,
        )

    async def search_similar_chunks(
        self,
        application: str,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = settings.RAG_TOP_K,
        score_threshold: float = settings.RAG_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search similar document chunks with strict application filter and optional document_id filter."""
        query_vector = self.embedding_service.embed_text(query)
        results = await self.qdrant_service.search_similar(
            query_vector=query_vector,
            application=application,
            document_id=document_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return results

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Perform RAG Chat completion: Vector Search -> Context Prompt -> LLM -> Response with PDF Page Citations."""
        app_name = str(request.application.value if hasattr(request.application, 'value') else request.application)
        doc_id = str(request.document_id) if request.document_id is not None else None

        # 1. Retrieve relevant context chunks for current tenant application (and optional document_id)
        context_chunks = await self.search_similar_chunks(
            application=app_name,
            query=request.message,
            document_id=doc_id,
            top_k=settings.RAG_TOP_K,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )

        # 2. Build RAG prompt with retrieved context
        rag_system, augmented_user_prompt = self.rag_prompt_service.build_rag_prompt(
            application=app_name,
            user_message=request.message,
            context_chunks=context_chunks,
        )

        # 3. Formulate ChatRequest for LLM Service
        modified_request = ChatRequest(
            application=app_name,
            user_id=request.user_id,
            message=augmented_user_prompt,
            document_id=doc_id,
        )

        # 4. Invoke LLM Service
        llm_response = await self.llm_service.generate_response(modified_request)

        # 5. Extract sources for citation metadata (including page_start, page_end, filename)
        sources = []
        if context_chunks:
            for chunk in context_chunks:
                sources.append({
                    "document_id": chunk.get("document_id"),
                    "title": chunk.get("title"),
                    "filename": chunk.get("filename"),
                    "page_start": chunk.get("page_start", 1),
                    "page_end": chunk.get("page_end", 1),
                    "chunk_index": chunk.get("chunk_index"),
                    "score": chunk.get("score"),
                })

        # 6. Check No-Context condition
        answer_message = llm_response.message
        if not context_chunks and not sources:
            answer_message = "Informasi tersebut tidak ditemukan dalam materi yang tersedia."

        return ChatResponse(
            application=app_name,
            model=llm_response.model,
            message=answer_message,
            provider=llm_response.provider,
            sources=sources,
        )
