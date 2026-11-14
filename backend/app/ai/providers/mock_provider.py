from typing import Any

from app.ai.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Offline provider that answers from real grounded facts (no LLM needed).

    When the orchestrator supplies structured ``grounding`` (intent, tool results, retrieved
    knowledge, memories) the reply is composed from those facts. It never echoes the prompt.
    """

    def __init__(self, model_name: str = "mock-support-agent-v1"):
        self.model_name = model_name

    def generate_response(
        self,
        conversation_subject: str,
        messages: list[dict[str, str]],
        prompt_override: str | None = None,
        **kwargs: Any,
    ) -> str:
        from app.ai.composer import Grounding, compose_reply  # lazy: composer imports the intent package

        grounding = kwargs.get("grounding")
        if isinstance(grounding, Grounding):
            return compose_reply(grounding)

        # An operator-supplied override on an ungrounded call is the message the operator wants sent.
        if prompt_override and prompt_override.strip():
            return prompt_override.strip()

        # Ungrounded call: there is no customer question to answer (the orchestrator always supplies
        # grounding when there is one), so open the conversation around its subject.
        return (
            f'Hi! I see you are reaching out about "{conversation_subject}". '
            "What would you like help with?"
        )
