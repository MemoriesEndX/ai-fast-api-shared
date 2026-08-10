from app.services.embedding_service import EmbeddingService


def test_embedding_service():
    service = EmbeddingService(dimension=384)
    vec = service.embed_text("Prosedur keselamatan kerja Safety Induction OWL")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert any(x != 0.0 for x in vec)


def test_embedding_batch():
    service = EmbeddingService(dimension=384)
    texts = ["Safety Induction", "Prosedur Cuti HR Corner"]
    vectors = service.embed_batch(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
