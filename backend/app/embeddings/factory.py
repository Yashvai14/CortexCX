from app.core.config import settings
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.mock_provider import MockEmbeddingProvider


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory to return the configured embedding provider."""
    provider_name = (settings.EMBEDDING_PROVIDER or "mock").lower().strip()
    dimension = settings.EMBEDDING_DIMENSION or 128

    if provider_name == "mock":
        return MockEmbeddingProvider(dimension=dimension)

    # Fallback to MockEmbeddingProvider
    return MockEmbeddingProvider(dimension=dimension)
