import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.rag_prompt_service import RAGPromptService
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger("ai_service.rag")


class RAGService:
    """Orchestrator for Document Indexing, Vector Search, and RAG Chat completions."""

    def __init__(
        self,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        qdrant_service: Optional[QdrantService] = None,
        rag_prompt_service: Optional[RAGPromptService] = None,
        llm_service: Optional[BaseLLMService] = None,
    ):
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()
        self.rag_prompt_service = rag_prompt_service or RAGPromptService()
        self.llm_service = llm_service or get_llm_service()

    async def index_document(
        self,
        application: str,
        document_id: str,
        title: str,
        text: str,
        content_id: Optional[str] = None,
        source_type: str = "document",
    ) -> Dict[str, Any]:
        """Chunk, embed, and index a document into Qdrant for a specific tenant application."""
        chunks = self.chunking_service.chunk_text(text)
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

    async def search_similar_chunks(
        self,
        application: str,
        query: str,
        top_k: int = settings.RAG_TOP_K,
        score_threshold: float = settings.RAG_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search similar document chunks with strict application filter."""
        query_vector = self.embedding_service.embed_text(query)
        results = await self.qdrant_service.search_similar(
            query_vector=query_vector,
            application=application,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return results

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Perform RAG Chat completion: Vector Search -> Context Prompt -> LLM -> Response with Sources."""
        app_name = str(request.application.value if hasattr(request.application, 'value') else request.application)

        # 1. Retrieve relevant context chunks for current tenant application
        context_chunks = await self.search_similar_chunks(
            application=app_name,
            query=request.message,
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
        )

        # 4. Invoke LLM Service
        llm_response = await self.llm_service.generate_response(modified_request)

        # 5. Extract sources for citation metadata
        sources = []
        if context_chunks:
            for chunk in context_chunks:
                sources.append({
                    "document_id": chunk.get("document_id"),
                    "title": chunk.get("title"),
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
