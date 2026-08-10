from typing import List, Dict, Any
from app.core.config import settings


class ChunkingService:
    """Service abstraction for document text chunking with configurable overlap."""

    def __init__(self, chunk_size: int = settings.CHUNK_SIZE, chunk_overlap: int = settings.CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split raw document text into indexed overlapping chunks."""
        if not text or not text.strip():
            return []

        cleaned_text = text.strip()
        chunks: List[Dict[str, Any]] = []

        # Simple character / word boundary sliding window chunker
        words = cleaned_text.split()
        if not words:
            return []

        # Estimate average words per chunk (~5 characters per word)
        words_per_chunk = max(1, self.chunk_size // 5)
        overlap_words = max(0, self.chunk_overlap // 5)

        step = max(1, words_per_chunk - overlap_words)
        
        chunk_idx = 0
        for i in range(0, len(words), step):
            chunk_words = words[i : i + words_per_chunk]
            chunk_str = " ".join(chunk_words)
            if chunk_str:
                chunks.append({
                    "chunk_index": chunk_idx,
                    "text": chunk_str,
                })
                chunk_idx += 1

            if i + words_per_chunk >= len(words):
                break

        return chunks
