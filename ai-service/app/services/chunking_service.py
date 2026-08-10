from typing import List, Dict, Any
from app.core.config import settings


class ChunkingService:
    """Service abstraction for document text chunking with page-aware tracking."""

    def __init__(self, chunk_size: int = settings.CHUNK_SIZE, chunk_overlap: int = settings.CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Legacy flat text chunker."""
        pages = [{"page": 1, "text": text}]
        return self.chunk_pages(pages)

    def chunk_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split page-structured document text into indexed overlapping chunks with page tracking."""
        if not pages:
            return []

        chunks: List[Dict[str, Any]] = []
        words_with_pages: List[Dict[str, Any]] = []

        for p in pages:
            page_num = p.get("page", 1)
            page_text = p.get("text", "").strip()
            if not page_text:
                continue

            for word in page_text.split():
                words_with_pages.append({
                    "word": word,
                    "page": page_num,
                })

        if not words_with_pages:
            return []

        words_per_chunk = max(1, self.chunk_size // 5)
        overlap_words = max(0, self.chunk_overlap // 5)
        step = max(1, words_per_chunk - overlap_words)

        chunk_idx = 0
        for i in range(0, len(words_with_pages), step):
            subset = words_with_pages[i : i + words_per_chunk]
            chunk_str = " ".join(item["word"] for item in subset)

            if chunk_str:
                page_start = subset[0]["page"]
                page_end = subset[-1]["page"]

                chunks.append({
                    "chunk_index": chunk_idx,
                    "text": chunk_str,
                    "page_start": page_start,
                    "page_end": page_end,
                })
                chunk_idx += 1

            if i + words_per_chunk >= len(words_with_pages):
                break

        return chunks
