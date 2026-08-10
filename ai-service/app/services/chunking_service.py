from typing import List, Dict, Any
from app.core.config import settings
from app.utils.timestamp_formatter import TimestampFormatter


class ChunkingService:
    """Service abstraction for document and video transcript chunking with timestamp tracking."""

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

    def chunk_transcript_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split timestamped transcript segments into indexed overlapping chunks with start/end timestamps."""
        if not segments:
            return []

        chunks: List[Dict[str, Any]] = []
        words_with_timestamps: List[Dict[str, Any]] = []

        for seg in segments:
            start_sec = float(seg.get("start", 0.0))
            end_sec = float(seg.get("end", 0.0))
            seg_text = seg.get("text", "").strip()
            if not seg_text:
                continue

            words = seg_text.split()
            if not words:
                continue

            # Distribute time proportionally across words in segment
            duration = max(0.1, end_sec - start_sec)
            time_per_word = duration / len(words)

            for w_idx, word in enumerate(words):
                w_start = start_sec + (w_idx * time_per_word)
                w_end = w_start + time_per_word
                words_with_timestamps.append({
                    "word": word,
                    "start": w_start,
                    "end": w_end,
                })

        if not words_with_timestamps:
            return []

        words_per_chunk = max(1, self.chunk_size // 5)
        overlap_words = max(0, self.chunk_overlap // 5)
        step = max(1, words_per_chunk - overlap_words)

        chunk_idx = 0
        for i in range(0, len(words_with_timestamps), step):
            subset = words_with_timestamps[i : i + words_per_chunk]
            chunk_str = " ".join(item["word"] for item in subset)

            if chunk_str:
                start_s = subset[0]["start"]
                end_s = subset[-1]["end"]

                chunks.append({
                    "chunk_index": chunk_idx,
                    "text": chunk_str,
                    "start_seconds": round(start_s, 2),
                    "end_seconds": round(end_s, 2),
                    "start_time": TimestampFormatter.seconds_to_timestamp(start_s),
                    "end_time": TimestampFormatter.seconds_to_timestamp(end_s),
                })
                chunk_idx += 1

            if i + words_per_chunk >= len(words_with_timestamps):
                break

        return chunks
