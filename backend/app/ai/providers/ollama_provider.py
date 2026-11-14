from typing import Any
import httpx

from app.ai.prompts import support_system_prompt

from app.ai.providers.base import BaseLLMProvider
from app.core.config import settings


class OllamaProvider(BaseLLMProvider):
    """Local Ollama inference provider for CortexCX."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float = 240.0,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_MODEL or "llama3.2"
        self.timeout = timeout

    def _convert_messages(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        store_name: str | None = None,
    ) -> list[dict[str, str]]:
        system_instruction = support_system_prompt(conversation_subject, store_name)
        if prompt_override:
            system_instruction += f"\n\n{prompt_override}"

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
        grounding = kwargs.get("grounding")
        formatted_messages = self._convert_messages(
            conversation_subject=conversation_subject,
            messages=messages,
            prompt_override=prompt_override,
            store_name=getattr(grounding, "store_name", None),
        )

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
                # System prompt + up to 7 policy passages + history needs ~3-4k tokens; a 4096 window silently
                # truncated the prompt. Reply budget is generous enough for an overview with a list and a table,
                # so answers are not cut off mid-sentence (finishing is also enforced in answer_format).
                "num_ctx": 8192,
                "num_predict": 700,
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

    def generate_chat(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        temperature: float = 0.6,
        max_tokens: int = 160,
    ) -> str:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system_instruction}, *messages],
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_ctx": 2048, "num_predict": max_tokens},
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
            return (resp.json().get("message", {}).get("content", "") or "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama chat completion failed: {type(e).__name__}") from None

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
            "keep_alive": "30m",
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


def warm_up_ollama() -> None:
    """Load the model into memory so the first customer message does not pay the cold-start cost."""
    import threading

    def _run():
        try:
            p = OllamaProvider(timeout=300.0)
            httpx.post(
                f"{p.base_url}/api/generate",
                json={"model": p.model_name, "prompt": "hi", "stream": False, "keep_alive": "30m",
                      "options": {"num_predict": 1}},
                timeout=300.0,
            )
        except Exception:
            pass  # the health endpoint reports Ollama status; warm-up is best effort

    threading.Thread(target=_run, daemon=True).start()
