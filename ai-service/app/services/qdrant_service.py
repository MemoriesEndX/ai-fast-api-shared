import logging
import math
import uuid
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("ai_service.qdrant")

COLLECTION_NAME = f"{settings.QDRANT_COLLECTION_PREFIX}_documents"


class QdrantService:
    """Service abstraction for Qdrant Vector Database operations."""

    _memory_store: Dict[str, List[Dict[str, Any]]] = {}  # Shared class-level memory store fallback

    def __init__(
        self,
        url: str = settings.QDRANT_URL,
        collection_name: str = COLLECTION_NAME,
        dimension: int = settings.EMBEDDING_DIMENSION,
    ):
        self.url = url
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = None

    def _get_client(self):
        """Lazy load QdrantClient with fast connection verification."""
        if self.client is None:
            try:
                from qdrant_client import QdrantClient
                temp_client = QdrantClient(url=self.url, timeout=1.0, check_compatibility=False)
                temp_client.get_collections()
                self.client = temp_client
                self._ensure_collection()
            except Exception as e:
                logger.warning(f"Could not connect to Qdrant server at {self.url} ({e}). Operating in memory mode.")
                self.client = "in_memory"

    def _ensure_collection(self):
        """Ensure collection and payload field indexes exist."""
        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                collections = self.client.get_collections().collections
                exists = any(c.name == self.collection_name for c in collections)
                if not exists:
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=models.VectorParams(
                            size=self.dimension,
                            distance=models.Distance.COSINE,
                        ),
                    )
                    logger.info(f"Created Qdrant collection: {self.collection_name}")

                    # Create payload indexes for fast filtering by application, document_id, and document_hash
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="application",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="document_id",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="document_hash",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
            except Exception as e:
                logger.error(f"Error ensuring Qdrant collection: {e}")

    async def get_document_by_hash(self, application: str, document_hash: str) -> Optional[Dict[str, Any]]:
        """Check if document vector with document_hash already exists."""
        self._get_client()
        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(key="application", match=models.MatchValue(value=application)),
                        models.FieldCondition(key="document_hash", match=models.MatchValue(value=document_hash)),
                    ]
                )
                res = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=query_filter,
                    limit=1,
                )
                if res and res[0]:
                    hit = res[0][0]
                    return hit.payload
            except Exception as e:
                logger.error(f"Error checking document hash: {e}")

        # In-memory check
        store = self._memory_store.get(self.collection_name, [])
        for item in store:
            p = item["payload"]
            if p.get("application") == application and p.get("document_hash") == document_hash:
                return p
        return None

    async def upsert_chunks(self, chunks_data: List[Dict[str, Any]]) -> bool:
        """Upsert document or video chunks into vector database."""
        self._get_client()

        if not chunks_data:
            return True

        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                points = []
                for item in chunks_data:
                    point_id = str(uuid.uuid4())
                    vector = item["vector"]
                    payload = {
                        "application": item["application"],
                        "source_type": item.get("source_type", "pdf"),
                        "document_id": str(item["document_id"]),
                        "content_id": item.get("content_id"),
                        "title": item.get("title", ""),
                        "filename": item.get("filename", ""),
                        "document_hash": item.get("document_hash", ""),
                        "version": item.get("version", "1.0"),
                        "chunk_index": item["chunk_index"],
                        "page_start": item.get("page_start", 1),
                        "page_end": item.get("page_end", 1),
                        "start_seconds": item.get("start_seconds"),
                        "end_seconds": item.get("end_seconds"),
                        "start_time": item.get("start_time"),
                        "end_time": item.get("end_time"),
                        "text": item["text"],
                    }
                    points.append(
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload,
                        )
                    )

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )
                logger.info(f"Successfully upserted {len(points)} chunks into Qdrant.")
                return True
            except Exception as e:
                logger.error(f"Failed to upsert to Qdrant: {e}")

        # Fallback in-memory storage for development / testing
        if self.collection_name not in self._memory_store:
            self._memory_store[self.collection_name] = []
        for item in chunks_data:
            self._memory_store[self.collection_name].append({
                "id": str(uuid.uuid4()),
                "vector": item["vector"],
                "payload": {
                    "application": item["application"],
                    "source_type": item.get("source_type", "pdf"),
                    "document_id": str(item["document_id"]),
                    "content_id": item.get("content_id"),
                    "title": item.get("title", ""),
                    "filename": item.get("filename", ""),
                    "document_hash": item.get("document_hash", ""),
                    "version": item.get("version", "1.0"),
                    "chunk_index": item["chunk_index"],
                    "page_start": item.get("page_start", 1),
                    "page_end": item.get("page_end", 1),
                    "start_seconds": item.get("start_seconds"),
                    "end_seconds": item.get("end_seconds"),
                    "start_time": item.get("start_time"),
                    "end_time": item.get("end_time"),
                    "text": item["text"],
                }
            })
        return True

    async def search_similar(
        self,
        query_vector: List[float],
        application: str,
        document_id: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = settings.RAG_TOP_K,
        score_threshold: float = settings.RAG_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search similar document or video/audio chunks strictly filtered by application tenant, optional document_id, and optional source_type."""
        self._get_client()

        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                
                must_filters = [
                    models.FieldCondition(
                        key="application",
                        match=models.MatchValue(value=application),
                    )
                ]
                if document_id:
                    must_filters.append(
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    )
                if source_type:
                    must_filters.append(
                        models.FieldCondition(
                            key="source_type",
                            match=models.MatchValue(value=source_type),
                        )
                    )

                query_filter = models.Filter(must=must_filters)

                if hasattr(self.client, "search"):
                    hits = self.client.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=score_threshold,
                    )
                else:
                    response = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=score_threshold,
                    )
                    hits = response.points

                results = []
                for hit in hits:
                    results.append({
                        "document_id": hit.payload.get("document_id"),
                        "content_id": hit.payload.get("content_id"),
                        "source_type": hit.payload.get("source_type", "pdf"),
                        "title": hit.payload.get("title", ""),
                        "filename": hit.payload.get("filename", ""),
                        "chunk_index": hit.payload.get("chunk_index"),
                        "page_start": hit.payload.get("page_start", 1),
                        "page_end": hit.payload.get("page_end", 1),
                        "start_seconds": hit.payload.get("start_seconds"),
                        "end_seconds": hit.payload.get("end_seconds"),
                        "start_time": hit.payload.get("start_time"),
                        "end_time": hit.payload.get("end_time"),
                        "text": hit.payload.get("text", ""),
                        "score": round(float(hit.score), 4),
                        "application": hit.payload.get("application"),
                    })
                return results
            except Exception as e:
                logger.error(f"Qdrant search error: {e}")

        # In-memory fallback similarity search
        store = self._memory_store.get(self.collection_name, [])
        results = []
        for item in store:
            payload = item["payload"]
            app_match = payload.get("application") == application
            doc_match = True if not document_id else str(payload.get("document_id")) == str(document_id)
            type_match = True if not source_type else payload.get("source_type") == source_type

            if app_match and doc_match and type_match:
                v1 = query_vector
                v2 = item["vector"]
                dot = sum(a * b for a, b in zip(v1, v2))
                norm1 = math.sqrt(sum(a * a for a in v1)) or 1.0
                norm2 = math.sqrt(sum(b * b for b in v2)) or 1.0
                sim = dot / (norm1 * norm2)

                results.append({
                    "document_id": payload.get("document_id"),
                    "content_id": payload.get("content_id"),
                    "source_type": payload.get("source_type", "pdf"),
                    "title": payload.get("title", ""),
                    "filename": payload.get("filename", ""),
                    "chunk_index": payload.get("chunk_index"),
                    "page_start": payload.get("page_start", 1),
                    "page_end": payload.get("page_end", 1),
                    "start_seconds": payload.get("start_seconds"),
                    "end_seconds": payload.get("end_seconds"),
                    "start_time": payload.get("start_time"),
                    "end_time": payload.get("end_time"),
                    "text": payload.get("text", ""),
                    "score": round(float(sim), 4),
                    "application": payload.get("application"),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def get_document_metadata(self, application: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve aggregated document metadata and chunks count by document_id and application."""
        self._get_client()

        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(key="application", match=models.MatchValue(value=application)),
                        models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id))),
                    ]
                )
                res = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=query_filter,
                    limit=100,
                )
                if res and res[0]:
                    points = res[0]
                    first = points[0].payload
                    return {
                        "document_id": str(document_id),
                        "application": application,
                        "title": first.get("title", ""),
                        "filename": first.get("filename", ""),
                        "source_type": first.get("source_type", "pdf"),
                        "status": "COMPLETED",
                        "document_hash": first.get("document_hash", ""),
                        "chunks_count": len(points),
                    }
            except Exception as e:
                logger.error(f"Error fetching document metadata from Qdrant: {e}")

        # In-memory fallback check
        store = self._memory_store.get(self.collection_name, [])
        matches = [
            item["payload"] for item in store
            if item["payload"].get("application") == application and str(item["payload"].get("document_id")) == str(document_id)
        ]
        if matches:
            first = matches[0]
            return {
                "document_id": str(document_id),
                "application": application,
                "title": first.get("title", ""),
                "filename": first.get("filename", ""),
                "source_type": first.get("source_type", "pdf"),
                "status": "COMPLETED",
                "document_hash": first.get("document_hash", ""),
                "chunks_count": len(matches),
            }
        return None

    async def list_documents(
        self,
        application: str,
        source_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List unique documents indexed under specified application tenant with pagination."""
        self._get_client()
        all_docs: Dict[str, Dict[str, Any]] = {}

        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                must_filters = [
                    models.FieldCondition(key="application", match=models.MatchValue(value=application))
                ]
                if source_type:
                    must_filters.append(
                        models.FieldCondition(key="source_type", match=models.MatchValue(value=source_type))
                    )
                query_filter = models.Filter(must=must_filters)
                res = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=query_filter,
                    limit=500,
                )
                if res and res[0]:
                    for point in res[0]:
                        p = point.payload
                        doc_id = str(p.get("document_id"))
                        if doc_id not in all_docs:
                            all_docs[doc_id] = {
                                "document_id": doc_id,
                                "application": application,
                                "title": p.get("title", ""),
                                "filename": p.get("filename", ""),
                                "source_type": p.get("source_type", "pdf"),
                                "status": "COMPLETED",
                                "document_hash": p.get("document_hash", ""),
                                "chunks_count": 1,
                            }
                        else:
                            all_docs[doc_id]["chunks_count"] += 1
            except Exception as e:
                logger.error(f"Error scrolling documents in Qdrant: {e}")

        # In-memory fallback listing
        if not all_docs:
            store = self._memory_store.get(self.collection_name, [])
            for item in store:
                p = item["payload"]
                if p.get("application") == application:
                    if source_type and p.get("source_type") != source_type:
                        continue
                    doc_id = str(p.get("document_id"))
                    if doc_id not in all_docs:
                        all_docs[doc_id] = {
                            "document_id": doc_id,
                            "application": application,
                            "title": p.get("title", ""),
                            "filename": p.get("filename", ""),
                            "source_type": p.get("source_type", "pdf"),
                            "status": "COMPLETED",
                            "document_hash": p.get("document_hash", ""),
                            "chunks_count": 1,
                        }
                    else:
                        all_docs[doc_id]["chunks_count"] += 1

        doc_list = list(all_docs.values())
        if status_filter:
            doc_list = [d for d in doc_list if d["status"].upper() == status_filter.upper()]

        total = len(doc_list)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = doc_list[start_idx:end_idx]

        return {
            "application": application,
            "page": page,
            "page_size": page_size,
            "total_documents": total,
            "documents": paginated,
        }

    async def delete_document(self, application: str, document_id: str) -> Dict[str, Any]:
        """Delete all vector points belonging to a specific document_id under a given application."""
        self._get_client()
        deleted_count = 0

        # Count chunks prior to deletion
        meta = await self.get_document_metadata(application, document_id)
        if meta:
            deleted_count = meta.get("chunks_count", 0)

        if self.client and self.client != "in_memory":
            try:
                from qdrant_client.http import models
                delete_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="application",
                            match=models.MatchValue(value=application),
                        ),
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        ),
                    ]
                )
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=delete_filter),
                )
                logger.info(f"Deleted document {document_id} ({deleted_count} chunks) under app {application} from Qdrant.")
                return {"success": True, "deleted_chunks": deleted_count}
            except Exception as e:
                logger.error(f"Error deleting document from Qdrant: {e}")

        # In-memory deletion fallback
        if self.collection_name in self._memory_store:
            original_len = len(self._memory_store[self.collection_name])
            self._memory_store[self.collection_name] = [
                item for item in self._memory_store[self.collection_name]
                if not (item["payload"].get("application") == application and str(item["payload"].get("document_id")) == str(document_id))
            ]
            new_len = len(self._memory_store[self.collection_name])
            if deleted_count == 0:
                deleted_count = original_len - new_len

        return {"success": True, "deleted_chunks": deleted_count}

    async def check_health(self) -> Dict[str, Any]:
        """Check Qdrant server connection health status."""
        self._get_client()
        if self.client and self.client != "in_memory":
            try:
                self.client.get_collections()
                return {"status": "ok", "service": "qdrant", "url": self.url}
            except Exception:
                pass
        return {"status": "degraded", "service": "qdrant", "url": self.url}


# Singleton instance
qdrant_service = QdrantService()

