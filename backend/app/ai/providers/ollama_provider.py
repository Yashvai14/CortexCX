from typing import Any
import httpx

from app.ai.providers.base import BaseLLMProvider
from app.core.config import settings


class OllamaProvider(BaseLLMProvider):
    """Local Ollama inference provider for CortexCX."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_MODEL or "llama3.2"
        self.timeout = timeout

    def _convert_messages(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
    ) -> list[dict[str, str]]:
        system_instruction = (
            f"You are a helpful, empathetic, and professional AI customer support assistant for CortexCX. "
            f"You are assisting a customer regarding: '{conversation_subject}'. "
            f"Provide clear, accurate, concise, and helpful answers based strictly on authoritative facts."
        )
        if prompt_override:
            system_instruction += f"\n\nContext & Instructions:\n{prompt_override}"

        formatted: list[dict[str, str]] = [
            {"role": "system", "content": system_instruction}
        ]

        for msg in messages:
            sender_type = msg.get("sender_type", "").lower()
            content = msg.get("content", "")

            if sender_type == "customer":
                formatted.append({"role": "user", "content": content})
            elif sender_type in ("agent", "ai"):
                formatted.append({"role": "assistant", "content": content})
            elif sender_type == "system":
                formatted.append({"role": "system", "content": content})
            else:
                formatted.append({"role": "user", "content": content})

        return formatted

    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        formatted_messages = self._convert_messages(
            conversation_subject=conversation_subject,
            messages=messages,
            prompt_override=prompt_override,
        )

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.3),
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            message = data.get("message", {})
            content = message.get("content", "")
            if not content:
                raise ValueError("Ollama returned empty completion content")
            return content.strip()

        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure Ollama is running."
            ) from None
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout}s"
            ) from None
        except Exception as e:
            raise RuntimeError(
                f"Ollama provider failed to generate response: {type(e).__name__} - {str(e)}"
            ) from None

    def generate_raw(
        self,
        prompt: str,
        system_instruction: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Direct raw prompt completion using Ollama."""
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("message", {}).get("content", "")
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"Ollama raw completion failed: {str(e)}") from None
