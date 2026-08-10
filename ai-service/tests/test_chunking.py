from app.services.chunking_service import ChunkingService


def test_chunking_service():
    service = ChunkingService(chunk_size=100, chunk_overlap=20)
    sample_text = "Standard Operating Procedure Safety Induction OWL LMS. " * 10
    chunks = service.chunk_text(sample_text)
    
    assert len(chunks) > 0
    assert "chunk_index" in chunks[0]
    assert "text" in chunks[0]
    assert chunks[0]["chunk_index"] == 0


def test_chunking_empty_text():
    service = ChunkingService()
    chunks = service.chunk_text("")
    assert chunks == []
