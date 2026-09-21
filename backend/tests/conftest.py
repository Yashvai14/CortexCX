import pytest
from app.core.config import settings

@pytest.fixture(autouse=True, scope="session")
def configure_test_settings():
    """Ensure standard unit test suites use deterministic mock provider,
    while live tests (e.g. test_live_system_verification.py) directly test OllamaProvider.
    """
    original_provider = settings.AI_PROVIDER
    settings.AI_PROVIDER = "mock"
    yield
    settings.AI_PROVIDER = original_provider
