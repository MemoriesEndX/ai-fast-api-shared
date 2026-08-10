import pytest
from fastapi import HTTPException
from app.utils.timestamp_formatter import TimestampFormatter
from app.services.video_service import VideoService
from app.services.chunking_service import ChunkingService
from app.services.transcription_service import TranscriptionService


def test_timestamp_formatter():
    assert TimestampFormatter.seconds_to_timestamp(0) == "00:00"
    assert TimestampFormatter.seconds_to_timestamp(272.5) == "04:32"
    assert TimestampFormatter.seconds_to_timestamp(3665) == "01:01:05"
    assert TimestampFormatter.format_time_range(272.5, 310.2) == "04:32 - 05:10"


def test_video_validation_extension():
    service = VideoService()
    with pytest.raises(HTTPException) as exc_info:
        service.validate_video_file("lecture.pdf", b"dummy")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_VIDEO_FORMAT"


def test_video_validation_empty_file():
    service = VideoService()
    with pytest.raises(HTTPException) as exc_info:
        service.validate_video_file("lecture.mp4", b"")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "EMPTY_VIDEO_FILE"


def test_timestamp_aware_chunking():
    chunker = ChunkingService()
    segments = [
        {"start": 0.0, "end": 10.0, "text": "Selamat datang di video Safety Induction."},
        {"start": 10.0, "end": 25.0, "text": "Bagian ini menerangkan APD helm keselamatan."},
    ]
    chunks = chunker.chunk_transcript_segments(segments)
    assert len(chunks) > 0
    c = chunks[0]
    assert "text" in c
    assert "start_seconds" in c
    assert "end_seconds" in c
    assert "start_time" in c
    assert "end_time" in c
