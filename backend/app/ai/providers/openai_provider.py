from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from app.ai.providers.base import BaseLLMProvider
from app.core.config import settings


class OpenAIProvider(BaseLLMProvider):
    """Production OpenAI LLM Provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
    ):
        if OpenAI is None and client is None:
            raise ImportError(
                "The 'openai' package is required to use OpenAIProvider. "
                "Install it with `pip install openai`."
            )

        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name or settings.OPENAI_MODEL or "gpt-4o-mini"

        if client is not None:
            self.client = client
        elif self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            raise ValueError(
                "OPENAI_API_KEY is not configured. Please set the OPENAI_API_KEY environment variable."
            )

    def _convert_messages(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
    ) -> list[dict[str, str]]:
        """Convert database message records into OpenAI chat completion messages."""
        system_instruction = (
            f"You are a helpful and professional customer support assistant for CortexCX. "
            f"You are assisting a customer regarding: '{conversation_subject}'. "
            f"Provide clear, empathetic, and direct assistance."
        )
        if prompt_override:
            system_instruction += f"\nSpecial Instruction: {prompt_override}"

        formatted_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_instruction}
        ]

        for msg in messages:
            sender_type = msg.get("sender_type", "").lower()
            content = msg.get("content", "")

            if sender_type == "customer":
                formatted_messages.append({"role": "user", "content": content})
            elif sender_type in ("agent", "ai"):
                formatted_messages.append(
                    {"role": "assistant", "content": content}
                )
            elif sender_type == "system":
                formatted_messages.append(
                    {"role": "system", "content": content}
                )
            else:
                formatted_messages.append({"role": "user", "content": content})

        return formatted_messages

    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate response using OpenAI Chat Completions API."""
        try:
            formatted_messages = self._convert_messages(
                conversation_subject=conversation_subject,
                messages=messages,
                prompt_override=prompt_override,
            )

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=formatted_messages,
                **kwargs,
            )

            if not response.choices or not response.choices[0].message.content:
                raise ValueError("Received empty response from OpenAI.")

            return response.choices[0].message.content.strip()

        except Exception as e:
            # Re-raise clean application-level RuntimeError without leaking credentials
            raise RuntimeError(
                f"OpenAI provider failed to generate response: {type(e).__name__} - {str(e)}"
            ) from None
