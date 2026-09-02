import hashlib
import math
import random

from app.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for testing and development."""

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        if not text:
            raise ValueError("Cannot generate embedding for empty text")

        # Create a deterministic 32-bit seed from text sha256 hash
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], byteorder="big")

        rng = random.Random(seed)
        # Generate random float vector
        raw_vector = [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]

        # L2-normalize the vector
        magnitude = math.sqrt(sum(x * x for x in raw_vector))
        if magnitude == 0:
            return [0.0] * self.dimension

        return [round(x / magnitude, 6) for x in raw_vector]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
