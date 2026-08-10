import io
import hashlib
import logging
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, status
from pypdf import PdfReader
from app.core.config import settings
from app.services.text_cleaning_service import TextCleaningService

logger = logging.getLogger("ai_service.pdf")


class PDFService:
    """Service abstraction for validating, parsing, and extracting text from text-based PDF documents."""

    def __init__(self, cleaning_service: TextCleaningService = None):
        self.cleaning_service = cleaning_service or TextCleaningService()

    def calculate_document_hash(self, file_bytes: bytes) -> str:
        """Calculate SHA-256 hash fingerprint of file contents."""
        return hashlib.sha256(file_bytes).hexdigest()

    def validate_pdf_file(self, filename: str, file_bytes: bytes):
        """Validate file size, extension, and PDF readability."""
        max_bytes = settings.MAX_PDF_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "PDF_SIZE_EXCEEDED",
                    "message": f"PDF file size exceeds maximum limit of {settings.MAX_PDF_SIZE_MB}MB."
                }
            )

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_FILE_TYPE",
                    "message": "Only .pdf file extension is supported."
                }
            )

        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "EMPTY_FILE",
                    "message": "Uploaded PDF file is empty."
                }
            )

    def extract_structured_text(self, file_bytes: bytes) -> Tuple[List[Dict[str, Any]], str, int]:
        """Extract page-by-page text from PDF stream. Returns (pages, document_hash, total_pages)."""
        doc_hash = self.calculate_document_hash(file_bytes)

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
        except Exception as e:
            logger.error(f"Corrupt or unreadable PDF: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CORRUPT_PDF",
                    "message": "Uploaded file is corrupt or not a valid PDF."
                }
            )

        pages_data: List[Dict[str, Any]] = []
        total_extracted_text_length = 0

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            try:
                raw_text = page.extract_text() or ""
            except Exception as e:
                logger.warning(f"Error extracting text from page {page_num}: {e}")
                raw_text = ""

            cleaned_text = self.cleaning_service.clean_text(raw_text)
            total_extracted_text_length += len(cleaned_text)

            if cleaned_text:
                pages_data.append({
                    "page": page_num,
                    "text": cleaned_text,
                })

        # Check for scanned PDF / missing text layer
        if total_extracted_text_length == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "PDF_NO_TEXT_LAYER",
                    "message": "PDF does not contain extractable text layer (Scanned or image-only PDF)."
                }
            )

        return pages_data, doc_hash, total_pages
