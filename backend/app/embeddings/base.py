from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    model_name: str = "unknown"

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        pass

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts."""
        pass

    # Asymmetric retrieval models (e.g. nomic) embed documents and queries differently.
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_text(text)
