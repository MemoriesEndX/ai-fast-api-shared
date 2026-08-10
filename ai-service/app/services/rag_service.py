import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.rag_prompt_service import RAGPromptService
from app.services.pdf_service import PDFService
from app.services.video_service import VideoService
from app.services.transcription_service import TranscriptionService
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger("ai_service.rag")


class RAGService:
    """Orchestrator for PDF & Video Ingestion, Vector Search, and RAG Chat completions."""

    _processing_status_store: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        qdrant_service: Optional[QdrantService] = None,
        rag_prompt_service: Optional[RAGPromptService] = None,
        pdf_service: Optional[PDFService] = None,
        video_service: Optional[VideoService] = None,
        transcription_service: Optional[TranscriptionService] = None,
        llm_service: Optional[BaseLLMService] = None,
    ):
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()
        self.rag_prompt_service = rag_prompt_service or RAGPromptService()
        self.pdf_service = pdf_service or PDFService()
        self.video_service = video_service or VideoService()
        self.transcription_service = transcription_service or TranscriptionService()
        self.llm_service = llm_service or get_llm_service()

    async def ingest_video_bytes(
        self,
        application: str,
        document_id: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        content_id: Optional[str] = None,
        version: str = "1.0",
        language: str = "id",
    ) -> Dict[str, Any]:
        """Process video: extract audio via FFmpeg, transcribe via Whisper, chunk with timestamps, embed, and index into Qdrant."""
        status_key = f"{application}_{document_id}"
        self._processing_status_store[status_key] = {
            "document_id": document_id,
            "application": application,
            "status": "processing",
            "progress": 20,
        }

        # 1. Extract audio & fingerprint hash via VideoService & FFmpeg
        audio_path, doc_hash, duration_sec = self.video_service.extract_audio_from_video(filename, file_bytes)

        # 2. Check for existing document hash idempotency
        existing = await self.qdrant_service.get_document_by_hash(application, doc_hash)
        if existing and existing.get("document_id") == str(document_id):
            logger.info(f"Video {filename} with hash {doc_hash[:8]} already indexed. Skipping duplicate.")
            self._processing_status_store[status_key] = {
                "document_id": document_id,
                "application": application,
                "status": "completed",
                "progress": 100,
            }
            return {
                "status": "already_indexed",
                "application": application,
                "document_id": document_id,
                "filename": filename,
                "document_hash": doc_hash,
                "duration_seconds": duration_sec,
                "segments": 0,
                "chunks": 0,
            }

        # 3. Transcribe audio to timestamped segments via TranscriptionService (faster-whisper)
        self._processing_status_store[status_key]["progress"] = 50
        segments = self.transcription_service.transcribe_audio_file(audio_path, language=language)

        # 4. Timestamp-aware chunking
        self._processing_status_store[status_key]["progress"] = 75
        chunks = self.chunking_service.chunk_transcript_segments(segments)

        if not chunks:
            self._processing_status_store[status_key]["status"] = "failed"
            return {
                "status": "failed",
                "application": application,
                "document_id": document_id,
                "chunks": 0,
                "message": "No text chunks generated from video transcript."
            }

        # 5. Generate vector embeddings
        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_service.embed_batch(texts)

        # 6. Assemble chunk payloads with timestamp metadata
        chunks_data = []
        for c, emb in zip(chunks, embeddings):
            chunks_data.append({
                "application": application,
                "document_id": str(document_id),
                "content_id": str(content_id) if content_id else None,
                "source_type": "video",
                "title": title,
                "filename": filename,
                "document_hash": doc_hash,
                "version": version,
                "chunk_index": c["chunk_index"],
                "start_seconds": c.get("start_seconds"),
                "end_seconds": c.get("end_seconds"),
                "start_time": c.get("start_time"),
                "end_time": c.get("end_time"),
                "text": c["text"],
                "vector": emb,
            })

        # 7. Upsert to Qdrant Vector DB
        success = await self.qdrant_service.upsert_chunks(chunks_data)

        self._processing_status_store[status_key] = {
            "document_id": document_id,
            "application": application,
            "status": "completed" if success else "failed",
            "progress": 100 if success else 0,
        }

        return {
            "status": "indexed" if success else "failed",
            "application": application,
            "document_id": document_id,
            "filename": filename,
            "document_hash": doc_hash,
            "duration_seconds": duration_sec,
            "segments": len(segments),
            "chunks": len(chunks),
        }

    async def get_video_processing_status(self, application: str, document_id: str) -> Dict[str, Any]:
        """Get processing status of video transcription job."""
        status_key = f"{application}_{document_id}"
        return self._processing_status_store.get(
            status_key,
            {
                "document_id": document_id,
                "application": application,
                "status": "completed",
                "progress": 100,
            }
        )

    async def reindex_video_bytes(
        self,
        application: str,
        document_id: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        content_id: Optional[str] = None,
        version: str = "1.0",
        language: str = "id",
    ) -> Dict[str, Any]:
        """Reindex video by first deleting old vector points then re-ingesting video audio transcript."""
        await self.delete_document(application, document_id)
        return await self.ingest_video_bytes(
            application=application,
            document_id=document_id,
            title=title,
            filename=filename,
            file_bytes=file_bytes,
            content_id=content_id,
            version=version,
            language=language,
        )

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
        self.pdf_service.validate_pdf_file(filename, file_bytes)
        pages_data, doc_hash, total_pages = self.pdf_service.extract_structured_text(file_bytes)

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

        chunks = self.chunking_service.chunk_pages(pages_data)
        if not chunks:
            return {
                "status": "error",
                "application": application,
                "document_id": document_id,
                "chunks": 0,
                "message": "No text chunks generated from PDF."
            }

        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_service.embed_batch(texts)

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
        """Index flat document text."""
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
        """Delete all document or video vector points under application tenant."""
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
        """Reindex PDF document by first clearing existing vectors, then re-ingesting PDF."""
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
        """Search similar document or video chunks with strict application filter and optional document_id filter."""
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
        """Perform RAG Chat completion: Vector Search -> Context Prompt -> LLM -> Response with PDF & Video Time Sources."""
        app_name = str(request.application.value if hasattr(request.application, 'value') else request.application)
        doc_id = str(request.document_id) if request.document_id is not None else None

        # 1. Retrieve relevant context chunks for current tenant application
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

        # 5. Extract sources for citation metadata (PDF page numbers & Video timestamps)
        sources = []
        if context_chunks:
            for chunk in context_chunks:
                source_item = {
                    "document_id": chunk.get("document_id"),
                    "title": chunk.get("title"),
                    "filename": chunk.get("filename"),
                    "source_type": chunk.get("source_type", "pdf"),
                    "chunk_index": chunk.get("chunk_index"),
                    "score": chunk.get("score"),
                }
                if chunk.get("source_type") == "video":
                    source_item["start_seconds"] = chunk.get("start_seconds")
                    source_item["end_seconds"] = chunk.get("end_seconds")
                    source_item["start_time"] = chunk.get("start_time", "00:00")
                    source_item["end_time"] = chunk.get("end_time", "00:00")
                else:
                    source_item["page_start"] = chunk.get("page_start", 1)
                    source_item["page_end"] = chunk.get("page_end", 1)

                sources.append(source_item)

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
