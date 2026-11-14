import httpx

from app.core.config import settings
from app.embeddings.base import BaseEmbeddingProvider

# Task prefixes required by the nomic-embed-text family for best retrieval quality.
_DOC_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Real dense embeddings from a local Ollama embedding model (default: nomic-embed-text, 768-d)."""

    def __init__(self, base_url: str | None = None, model_name: str | None = None, timeout: float = 120.0, batch_size: int = 16):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.timeout = timeout
        self.batch_size = batch_size
        self._prefixed = "nomic" in self.model_name.lower()

    def _embed_batch(self, inputs: list[str]) -> list[list[float]]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model_name, "input": inputs, "keep_alive": "30m"},
                )
                resp.raise_for_status()
                vectors = resp.json().get("embeddings") or []
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url} for embeddings") from None
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama embedding request failed ({e.response.status_code}): {e.response.text[:200]}") from None
        if len(vectors) != len(inputs):
            raise RuntimeError(f"Ollama returned {len(vectors)} embeddings for {len(inputs)} inputs")
        want = settings.EMBEDDING_DIMENSION
        if vectors and len(vectors[0]) != want:
            raise RuntimeError(
                f"Embedding model '{self.model_name}' returns {len(vectors[0])}-d vectors but EMBEDDING_DIMENSION={want}"
            )
        return vectors

    def _embed_many(self, texts: list[str], prefix: str) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = [prefix + t for t in texts[i : i + self.batch_size]]
            out.extend(self._embed_batch(batch))
        return out

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")
        return self._embed_many([text], _DOC_PREFIX if self._prefixed else "")[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, _DOC_PREFIX if self._prefixed else "")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, _DOC_PREFIX if self._prefixed else "")

    def embed_query(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")
        return self._embed_many([text], _QUERY_PREFIX if self._prefixed else "")[0]
