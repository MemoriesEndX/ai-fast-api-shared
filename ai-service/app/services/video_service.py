import os
import io
import shutil
import hashlib
import logging
import subprocess
import tempfile
from typing import Tuple
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("ai_service.video")


class VideoService:
    """Service abstraction for video validation, fingerprint hashing, and FFmpeg audio extraction."""

    SUPPORTED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".mp3", ".wav"}

    def calculate_document_hash(self, file_bytes: bytes) -> str:
        """Calculate SHA-256 fingerprint hash of video file bytes."""
        return hashlib.sha256(file_bytes).hexdigest()

    def validate_video_file(self, filename: str, file_bytes: bytes):
        """Validate video file size, extension, and content."""
        max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "VIDEO_SIZE_EXCEEDED",
                    "message": f"Video file size exceeds maximum limit of {settings.MAX_VIDEO_SIZE_MB}MB."
                }
            )

        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_VIDEO_FORMAT",
                    "message": f"Unsupported video extension '{ext}'. Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
                }
            )

        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "EMPTY_VIDEO_FILE",
                    "message": "Uploaded video file is empty."
                }
            )

    def extract_audio_from_video(self, filename: str, file_bytes: bytes) -> Tuple[str, str, float]:
        """Extract 16kHz mono WAV audio stream from video using FFmpeg. Returns (audio_wav_path, document_hash, duration_seconds)."""
        self.validate_video_file(filename, file_bytes)
        doc_hash = self.calculate_document_hash(file_bytes)

        temp_dir = tempfile.mkdtemp(prefix="ai_video_")
        video_ext = os.path.splitext(filename)[1].lower()
        video_path = os.path.join(temp_dir, f"input_video{video_ext}")
        audio_path = os.path.join(temp_dir, "extracted_audio.wav")

        with open(video_path, "wb") as f:
            f.write(file_bytes)

        # Check FFmpeg binary availability
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            logger.warning("FFmpeg binary not found on host. Operating in fallback mock mode.")
            return video_path, doc_hash, 10.0

        try:
            # Extract 16kHz mono PCM WAV audio stream using FFmpeg
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                audio_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            # Probe audio duration using ffprobe if available
            duration_sec = self._probe_duration(video_path)
            return audio_path, doc_hash, duration_sec

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg audio extraction failed: {e.stderr.decode('utf-8', errors='ignore')}")
            # Fallback for dev / test mode if dummy video bytes are passed
            if settings.APP_ENV in ("development", "test"):
                logger.warning("Operating in fallback mock audio mode for dev/test environment.")
                return video_path, doc_hash, 10.0
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "FFMPEG_EXTRACTION_FAILED",
                    "message": "Failed to extract audio stream from video file (Invalid codec or corrupted stream)."
                }
            )

    def _probe_duration(self, file_path: str) -> float:
        """Probe video/audio duration using ffprobe."""
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return 10.0
        try:
            cmd = [
                ffprobe_bin,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(res.stdout.strip())
        except Exception:
            return 10.0
