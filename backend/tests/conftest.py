import pytest
from app.core.config import settings

@pytest.fixture(autouse=True, scope="session")
def configure_test_settings():
    """Ensure standard unit test suites use deterministic mock provider,
    while live tests (e.g. test_live_system_verification.py) directly test OllamaProvider.
    """
    original_provider = settings.AI_PROVIDER
    original_embedding = settings.EMBEDDING_PROVIDER
    settings.AI_PROVIDER = "mock"
    settings.EMBEDDING_PROVIDER = "mock"  # deterministic, offline; real embeddings are covered by test_rag_live.py
    original_cache = settings.RAG_CACHE_ENABLED
    settings.RAG_CACHE_ENABLED = False  # tests count LLM calls; cache behaviour has its own tests
    original_tg_token = settings.TELEGRAM_BOT_TOKEN
    settings.TELEGRAM_BOT_TOKEN = None  # never call the real Telegram API from tests
    yield
    settings.TELEGRAM_BOT_TOKEN = original_tg_token
    settings.RAG_CACHE_ENABLED = original_cache
    settings.AI_PROVIDER = original_provider
    settings.EMBEDDING_PROVIDER = original_embedding
