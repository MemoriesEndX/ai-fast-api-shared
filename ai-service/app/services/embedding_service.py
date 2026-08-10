import logging
import math
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger("ai_service.embedding")


class EmbeddingService:
    """Service abstraction for generating dense vector embeddings using fastembed or fallback encoder."""

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        dimension: int = settings.EMBEDDING_DIMENSION,
    ):
        self.model_name = model_name
        self.dimension = dimension
        self._model = None

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
        """Generate vector embeddings for a list of texts."""
        if not texts:
            return []

        self._init_model()

        if self._model != "fallback" and hasattr(self._model, "embed"):
            try:
                embeddings_gen = self._model.embed(texts)
                embeddings = [list(vec) for vec in embeddings_gen]
                
                # Dimension validation
                if embeddings and len(embeddings[0]) != self.dimension:
                    logger.warning(
                        f"Generated vector dimension {len(embeddings[0])} differs from settings {self.dimension}. "
                        "Updating expected dimension."
                    )
                    self.dimension = len(embeddings[0])
                
                return embeddings
            except Exception as exc:
                logger.error(f"Error during fastembed inference: {exc}")

        # Deterministic CPU hashing fallback encoder for test / offline mode
        logger.info("Using deterministic fallback vector embedding encoder.")
        results = []
        for text in texts:
            vec = [0.0] * self.dimension
            for i, char in enumerate(text.lower()):
                idx = (ord(char) * (i + 1)) % self.dimension
                vec[idx] += math.sin(ord(char))
            # L2 Normalize
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            results.append([round(x / norm, 6) for x in vec])
        return results
