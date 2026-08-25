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


def test_candidate_embedding_caching_and_correctness():
    """Phase 20.7: Verify embedding in-memory caching produces identical vectors with cache reuse."""
    service = EmbeddingService(dimension=384)
    candidate_catalog = [
        "Safety Induction 2026 - K3 Awareness & APD Compliance",
        "Laravel 11 Advanced Architecture & Microservices",
        "PostgreSQL High Availability & Replication",
        "Confined Space Safety Procedures & Permits"
    ]

    # Initial call - populates cache
    vectors_1 = service.embed_batch(candidate_catalog)
    assert len(vectors_1) == len(candidate_catalog)
    assert len(service._cache) == len(candidate_catalog)

    # Repeat call - 100% cache hit, identical vectors
    vectors_2 = service.embed_batch(candidate_catalog)
    assert len(vectors_2) == len(candidate_catalog)
    for v1, v2 in zip(vectors_1, vectors_2):
        assert v1 == v2

    # Partial cache hit test (3 cached + 1 new candidate)
    mixed_catalog = list(candidate_catalog[:3]) + ["New Unseen Candidate Module 101"]
    vectors_3 = service.embed_batch(mixed_catalog)
    assert len(vectors_3) == 4
    for i in range(3):
        assert vectors_3[i] == vectors_1[i]
    assert len(service._cache) == 5

