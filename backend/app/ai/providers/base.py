from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response given the conversation subject and message history."""
        pass

    def generate_chat(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        temperature: float = 0.6,
        max_tokens: int = 160,
    ) -> str:
        """Plain chat completion with a caller-supplied system prompt (used for ordinary conversation, where the
        document-grounded prompt of generate_response does not apply). Providers without it raise, and the caller
        falls back to deterministic replies."""
        raise NotImplementedError
