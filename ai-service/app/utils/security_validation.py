import re
import os
import logging
from typing import Set
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("ai_service.utils.security_validation")

PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\.[/\\])|([/\\]etc[/\\])|(^[a-zA-Z]:[/\\])|(file://)", re.IGNORECASE)

ALLOWED_PDF_EXTENSIONS: Set[str] = {".pdf"}
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mov", ".mkv"}
ALLOWED_AUDIO_EXTENSIONS: Set[str] = {".wav", ".mp3", ".m4a"}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename and block path traversal attempts."""
    if not filename:
        return "uploaded_file"
    
    if PATH_TRAVERSAL_PATTERN.search(filename):
        logger.warning(f"Path traversal attempt detected in filename: '{filename}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_REQUEST",
                "message": "Security Error: Path traversal characters or unsafe paths are forbidden."
            }
        )

    base = os.path.basename(filename.strip())
    # Remove null bytes or control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", base)
    return cleaned if cleaned else "uploaded_file"


def validate_upload_file(filename: str, file_bytes: bytes, allowed_extensions: Set[str], max_size_mb: int, category: str = "document"):
    """Audit file upload for extension, empty content, and size limits."""
    clean_name = sanitize_filename(filename)
    ext = os.path.splitext(clean_name)[1].lower()

    if ext not in allowed_extensions:
        logger.warning(f"Invalid file extension '{ext}' for category '{category}'. Allowed: {allowed_extensions}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_FILE_TYPE" if category == "pdf" else ("INVALID_VIDEO_FORMAT" if category == "video" else "INVALID_FILE_TYPE"),
                "message": f"Unsupported file type '{ext}'. Allowed extensions: {', '.join(allowed_extensions)}"
            }
        )

    if not file_bytes or len(file_bytes) == 0:
        logger.warning(f"Empty file uploaded: '{clean_name}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EMPTY_FILE" if category == "pdf" else ("EMPTY_VIDEO_FILE" if category == "video" else "EMPTY_FILE"),
                "message": f"Uploaded {category} file is empty (0 bytes)."
            }
        )

    max_bytes = max_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        logger.warning(f"File size {len(file_bytes)} bytes exceeds limit of {max_size_mb} MB for '{clean_name}'.")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"File size exceeds maximum allowed limit of {max_size_mb} MB."
            }
        )

    return clean_name
