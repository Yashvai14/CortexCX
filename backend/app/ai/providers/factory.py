from app.ai.providers.base import BaseLLMProvider
from app.ai.providers.mock_provider import MockLLMProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings


def get_llm_provider() -> BaseLLMProvider:
    """Factory to retrieve the active LLM provider instance."""
    provider_name = (settings.AI_PROVIDER or "mock").lower().strip()
    if provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    return MockLLMProvider()

