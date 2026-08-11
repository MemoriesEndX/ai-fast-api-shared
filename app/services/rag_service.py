import os
import shutil
import logging
import json
import hashlib
import tempfile
import uuid
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
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
from app.mcp import mcp_server
from app.mcp.client import MCPClient
from app.tools.auth import UserAuthContext

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
        audio_path, doc_hash, duration_sec, temp_dir = self.video_service.extract_audio_from_video(filename, file_bytes)

        try:
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
        finally:
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

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
        res = await self.qdrant_service.delete_document(application, document_id)
        if isinstance(res, dict):
            is_success = res.get("success", False)
            deleted_chunks = res.get("deleted_chunks", 0)
        else:
            is_success = bool(res)
            deleted_chunks = 0
        return {
            "status": "deleted" if is_success else "failed",
            "success": is_success,
            "application": application,
            "document_id": document_id,
            "deleted_chunks": deleted_chunks,
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

    async def ingest_audio_bytes(
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
        """Validate, transcribe audio via Whisper, chunk with timestamp metadata, embed, and index into Qdrant."""
        doc_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = await self.qdrant_service.get_document_by_hash(application, doc_hash)
        if existing and existing.get("document_id") == str(document_id):
            logger.info(f"Audio file {filename} with hash {doc_hash[:8]} already indexed. Skipping duplicate.")
            return {
                "status": "already_indexed",
                "application": application,
                "document_id": document_id,
                "filename": filename,
                "document_hash": doc_hash,
                "segments": 0,
                "chunks": 0,
            }

        temp_dir = tempfile.mkdtemp(prefix="ai_audio_")
        audio_ext = os.path.splitext(filename)[1].lower()
        audio_path = os.path.join(temp_dir, f"input_audio{audio_ext}")
        with open(audio_path, "wb") as f:
            f.write(file_bytes)

        try:
            segments = self.transcription_service.transcribe_audio_file(audio_path, language=language)
            chunks = self.chunking_service.chunk_transcript_segments(segments)

            if not chunks:
                return {
                    "status": "failed",
                    "application": application,
                    "document_id": document_id,
                    "chunks": 0,
                    "message": "No text chunks generated from audio transcript."
                }

            texts = [c["text"] for c in chunks]
            embeddings = self.embedding_service.embed_batch(texts)

            chunks_data = []
            for c, emb in zip(chunks, embeddings):
                chunks_data.append({
                    "application": application,
                    "document_id": str(document_id),
                    "content_id": str(content_id) if content_id else None,
                    "source_type": "audio",
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

            success = await self.qdrant_service.upsert_chunks(chunks_data)
            return {
                "status": "indexed" if success else "failed",
                "application": application,
                "document_id": document_id,
                "filename": filename,
                "document_hash": doc_hash,
                "segments": len(segments),
                "chunks": len(chunks),
            }
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def ingest_knowledge(
        self,
        application: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        document_id: Optional[str] = None,
        source_type: Optional[str] = None,
        content_id: Optional[str] = None,
        version: str = "1.0",
        language: str = "id",
    ) -> Dict[str, Any]:
        """Unified entry point for PDF, Video, and Audio knowledge ingestion."""
        doc_id = document_id or str(uuid.uuid4())
        ext = os.path.splitext(filename)[1].lower()

        # Determine source_type if not explicitly provided
        if not source_type:
            if ext in (".pdf",):
                source_type = "pdf"
            elif ext in (".mp4", ".webm", ".mkv", ".mov", ".avi"):
                source_type = "video"
            elif ext in (".mp3", ".wav", ".m4a"):
                source_type = "audio"
            else:
                source_type = "pdf"

        doc_hash = hashlib.sha256(file_bytes).hexdigest()

        # SHA-256 duplicate detection check
        existing = await self.qdrant_service.get_document_by_hash(application, doc_hash)
        if existing:
            logger.info(f"Duplicate document hash detected for {filename} under tenant {application}.")
            return {
                "status": "duplicate",
                "document_id": existing.get("document_id", doc_id),
                "document_hash": doc_hash,
                "title": title,
                "filename": filename,
                "source_type": source_type,
                "application": application,
                "chunks_indexed": 0,
                "message": "Document with identical SHA-256 hash already exists."
            }

        # Dispatch to appropriate ingestion pipeline
        if source_type == "pdf":
            self.pdf_service.validate_pdf_file(filename, file_bytes)
            pages_data, doc_hash, total_pages = self.pdf_service.extract_structured_text(file_bytes)
            chunks = self.chunking_service.chunk_pages(pages_data)

            if not chunks:
                return {
                    "status": "failed",
                    "document_id": doc_id,
                    "document_hash": doc_hash,
                    "title": title,
                    "filename": filename,
                    "source_type": "pdf",
                    "application": application,
                    "chunks_indexed": 0,
                    "message": "No text chunks extracted from PDF."
                }

            texts = [c["text"] for c in chunks]
            embeddings = self.embedding_service.embed_batch(texts)

            chunks_data = []
            for c, emb in zip(chunks, embeddings):
                chunks_data.append({
                    "application": application,
                    "document_id": doc_id,
                    "content_id": content_id,
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
                "status": "completed" if success else "failed",
                "document_id": doc_id,
                "document_hash": doc_hash,
                "title": title,
                "filename": filename,
                "source_type": "pdf",
                "application": application,
                "chunks_indexed": len(chunks) if success else 0,
                "message": "Knowledge PDF processed and indexed successfully." if success else "Failed to index PDF chunks into Qdrant."
            }

        elif source_type == "video":
            res = await self.ingest_video_bytes(
                application=application,
                document_id=doc_id,
                title=title,
                filename=filename,
                file_bytes=file_bytes,
                content_id=content_id,
                version=version,
                language=language,
            )
            return {
                "status": "completed" if res.get("status") in ("indexed", "already_indexed") else "failed",
                "document_id": doc_id,
                "document_hash": doc_hash,
                "title": title,
                "filename": filename,
                "source_type": "video",
                "application": application,
                "chunks_indexed": res.get("chunks", 0),
                "message": "Knowledge Video processed and indexed successfully."
            }

        elif source_type == "audio":
            res = await self.ingest_audio_bytes(
                application=application,
                document_id=doc_id,
                title=title,
                filename=filename,
                file_bytes=file_bytes,
                content_id=content_id,
                version=version,
                language=language,
            )
            return {
                "status": "completed" if res.get("status") in ("indexed", "already_indexed") else "failed",
                "document_id": doc_id,
                "document_hash": doc_hash,
                "title": title,
                "filename": filename,
                "source_type": "audio",
                "application": application,
                "chunks_indexed": res.get("chunks", 0),
                "message": "Knowledge Audio processed and indexed successfully."
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported source type '{source_type}'."}
            )

    async def get_knowledge_document(self, application: str, document_id: str) -> Dict[str, Any]:
        """Get document status and metadata."""
        meta = await self.qdrant_service.get_document_metadata(application, document_id)
        if not meta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document '{document_id}' not found for tenant '{application}'."}
            )
        return meta

    async def list_knowledge_documents(
        self,
        application: str,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List knowledge documents with pagination."""
        return await self.qdrant_service.list_documents(
            application=application,
            source_type=source_type,
            status_filter=status,
            page=page,
            page_size=page_size,
        )

    async def reindex_knowledge_document(
        self,
        application: str,
        document_id: str,
        title: str,
        filename: str,
        file_bytes: bytes,
        source_type: Optional[str] = None,
        content_id: Optional[str] = None,
        version: str = "1.1",
        language: str = "id",
    ) -> Dict[str, Any]:
        """Atomic reindex: process new file first; if successful, update Qdrant; if processing fails, old knowledge is preserved."""
        # 1. Process new file into chunks without purging existing vector points
        ext = os.path.splitext(filename)[1].lower()
        target_source_type = source_type or ("pdf" if ext == ".pdf" else ("video" if ext in (".mp4", ".webm", ".mkv", ".mov", ".avi") else "audio"))

        if target_source_type == "pdf":
            self.pdf_service.validate_pdf_file(filename, file_bytes)
            pages_data, doc_hash, total_pages = self.pdf_service.extract_structured_text(file_bytes)
            chunks = self.chunking_service.chunk_pages(pages_data)
            if not chunks:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "PROCESSING_FAILED", "message": "Failed to chunk new PDF."})
            texts = [c["text"] for c in chunks]
            embeddings = self.embedding_service.embed_batch(texts)
            chunks_data = []
            for c, emb in zip(chunks, embeddings):
                chunks_data.append({
                    "application": application,
                    "document_id": document_id,
                    "content_id": content_id,
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
        else:
            # For video/audio, perform transcription & chunking
            temp_dir = tempfile.mkdtemp(prefix="reindex_")
            try:
                temp_file = os.path.join(temp_dir, f"input_{filename}")
                with open(temp_file, "wb") as f:
                    f.write(file_bytes)
                doc_hash = hashlib.sha256(file_bytes).hexdigest()
                segments = self.transcription_service.transcribe_audio_file(temp_file, language=language)
                chunks = self.chunking_service.chunk_transcript_segments(segments)
                texts = [c["text"] for c in chunks]
                embeddings = self.embedding_service.embed_batch(texts)
                chunks_data = []
                for c, emb in zip(chunks, embeddings):
                    chunks_data.append({
                        "application": application,
                        "document_id": document_id,
                        "content_id": content_id,
                        "source_type": target_source_type,
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
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        # 2. Verify new processing succeeded before replacing old knowledge
        await self.delete_document(application, document_id)
        success = await self.qdrant_service.upsert_chunks(chunks_data)

        return {
            "status": "completed" if success else "failed",
            "document_id": document_id,
            "document_hash": doc_hash,
            "title": title,
            "filename": filename,
            "source_type": target_source_type,
            "application": application,
            "chunks_indexed": len(chunks_data) if success else 0,
            "message": "Knowledge document reindexed successfully."
        }

    async def search_similar_chunks(
        self,
        application: str,
        query: str,
        document_id: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = settings.RAG_TOP_K,
        score_threshold: float = settings.RAG_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search similar document or video/audio chunks with strict application filter and optional document_id or source_type filter."""
        query_vector = self.embedding_service.embed_text(query)
        results = await self.qdrant_service.search_similar(
            query_vector=query_vector,
            application=application,
            document_id=document_id,
            source_type=source_type,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return results

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Perform Unified AI Agent chat completion across LMS Tools, PDF RAG, Video RAG, and Recommendation Engine."""
        from app.agent.orchestrator import agent_orchestrator
        return await agent_orchestrator.process_chat(request)

