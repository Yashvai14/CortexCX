from typing import Any

from app.ai.prompts import support_system_prompt

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
        store_name: str | None = None,
    ) -> list[dict[str, str]]:
        """Convert database message records into OpenAI chat completion messages."""
        system_instruction = support_system_prompt(conversation_subject, store_name)
        if prompt_override:
            system_instruction += f"\n\n{prompt_override}"

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

    def generate_chat(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        temperature: float = 0.6,
        max_tokens: int = 160,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_instruction}, *messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("empty response")
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI chat completion failed: {type(e).__name__}") from None

    def generate_raw(self, prompt: str, system_instruction: str | None = None, **kwargs: Any) -> str:
        """Direct completion (used for the router's JSON classification)."""
        return self.generate_chat(system_instruction or "", [{"role": "user", "content": prompt}],
                                  temperature=kwargs.get("temperature", 0.0), max_tokens=kwargs.get("max_tokens", 200))

    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate response using OpenAI Chat Completions API."""
        grounding = kwargs.pop("grounding", None)
        try:
            formatted_messages = self._convert_messages(
                conversation_subject=conversation_subject,
                messages=messages,
                prompt_override=prompt_override,
                store_name=getattr(grounding, "store_name", None),
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
