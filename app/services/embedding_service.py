import logging
import math
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger("ai_service.embedding")


class EmbeddingService:
    """Service abstraction for generating dense vector embeddings using fastembed or fallback encoder with in-memory caching."""

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        dimension: int = settings.EMBEDDING_DIMENSION,
        cache_size: int = 4096,
    ):
        self.model_name = model_name
        self.dimension = dimension
        self.cache_size = cache_size
        self._model = None
        self._cache: dict = {}

    def _init_model(self):
        """Lazy load fastembed TextEmbedding model."""
        if self._model is None:
            if settings.APP_ENV in ("development", "test"):
                # Use deterministic fast CPU fallback in dev/test mode to prevent blocking on network downloads
                self._model = "fallback"
                return
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                logger.info(f"Initialized fastembed model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to load fastembed model ({e}). Using CPU deterministic fallback encoder.")
                self._model = "fallback"

    def embed_text(self, text: str) -> List[float]:
        """Generate a float vector embedding for a single string text."""
        vectors = self.embed_batch([text])
        return vectors[0] if vectors else [0.0] * self.dimension

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a list of texts with in-memory caching."""
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        for idx, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results[idx] = cached
            else:
                missing_indices.append(idx)
                missing_texts.append(text)

        if missing_texts:
            self._init_model()
            computed_vectors: List[List[float]] = []

            if self._model != "fallback" and hasattr(self._model, "embed"):
                try:
                    embeddings_gen = self._model.embed(missing_texts)
                    computed_vectors = [list(vec) for vec in embeddings_gen]

                    # Dimension validation
                    if computed_vectors and len(computed_vectors[0]) != self.dimension:
                        logger.warning(
                            f"Generated vector dimension {len(computed_vectors[0])} differs from settings {self.dimension}. "
                            "Updating expected dimension."
                        )
                        self.dimension = len(computed_vectors[0])
                except Exception as exc:
                    logger.error(f"Error during fastembed inference: {exc}")
                    computed_vectors = []

            if not computed_vectors:
                # Deterministic CPU hashing fallback encoder for test / offline mode
                for text in missing_texts:
                    vec = [0.0] * self.dimension
                    for i, char in enumerate(text.lower()):
                        char_idx = (ord(char) * (i + 1)) % self.dimension
                        vec[char_idx] += math.sin(ord(char))
                    # L2 Normalize
                    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
                    computed_vectors.append([round(x / norm, 6) for x in vec])

            for orig_idx, text, vec in zip(missing_indices, missing_texts, computed_vectors):
                results[orig_idx] = vec
                if len(self._cache) >= self.cache_size:
                    try:
                        self._cache.pop(next(iter(self._cache)))
                    except (KeyError, StopIteration):
                        pass
                self._cache[text] = vec

        return [r for r in results if r is not None]


# Singleton instance
embedding_service = EmbeddingService()
