"""Live RAG check with REAL embeddings (nomic-embed-text via Ollama). Skipped when Ollama is not reachable."""
import httpx
import pytest

from app.core.config import settings
from tests.test_rag_pipeline import POLICY_TEXT, _upload, _wait, _workspace, client


def _ollama_has_embedder() -> bool:
    try:
        tags = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2).json()
        return any(settings.EMBEDDING_MODEL in m.get("name", "") for m in tags.get("models", []))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ollama_has_embedder(), reason="Ollama embedding model not available")


@pytest.fixture()
def real_embeddings():
    old = settings.EMBEDDING_PROVIDER
    settings.EMBEDDING_PROVIDER = "ollama"
    yield
    settings.EMBEDDING_PROVIDER = old


def test_dense_retrieval_understands_paraphrases(real_embeddings):
    ws, H, src = _workspace()
    doc = _wait(H, _upload(H, src, "help.txt", POLICY_TEXT.encode()).json()["id"])
    assert doc["status"] == "completed", doc

    chunks = client.get(f"/knowledge/documents/{doc['id']}/chunks", headers=H).json()
    assert all(c["embedding_model"] == settings.EMBEDDING_MODEL for c in chunks)

    # No word overlap with the passage ("send back", "guaranteed"), so only dense retrieval can find these.
    cases = {
        "how many days do I have to send something back": "Returns",
        "is the rucksack guaranteed for life": "Warranty",
        "what do you charge for delivery": "Shipping",
    }
    for query, section in cases.items():
        top = client.post("/knowledge/search", headers=H, json={"query": query, "top_k": 3}).json()["results"]
        assert top and top[0]["section"] == section, (query, top[:1])
        assert top[0]["dense_score"] is not None and top[0]["dense_score"] > settings.RAG_DENSE_FLOOR

    # Unrelated question: the relevance gate returns nothing rather than the "least bad" chunk.
    assert client.post("/knowledge/search", headers=H, json={"query": "what is the capital of France", "top_k": 3}).json()["total"] == 0
