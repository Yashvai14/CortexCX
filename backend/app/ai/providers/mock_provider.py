from typing import Any

from app.ai.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for AI support responses."""

    def __init__(self, model_name: str = "mock-support-agent-v1"):
        self.model_name = model_name

    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        if prompt_override:
            return f"[AI Assistant Override] {prompt_override}"

        last_message = (
            messages[-1]["content"] if messages else "General inquiry"
        )
        return (
            f"Hello! This is your AI Support Assistant regarding '{conversation_subject}'. "
            f"I have reviewed your message: \"{last_message}\". "
            f"Our team is actively assisting you, and I am here to help resolve your inquiry."
        )
