import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.providers.base import BaseLLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.providers.mock_provider import MockLLMProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_factory_provider_selection():
    # 1. Default / mock provider
    with patch.object(settings, "AI_PROVIDER", "mock"):
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)
        assert isinstance(provider, BaseLLMProvider)

    # 2. OpenAI provider
    with patch.object(settings, "AI_PROVIDER", "openai"), patch.object(
        settings, "OPENAI_API_KEY", "sk-mock-test-key-12345"
    ):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)
        assert isinstance(provider, BaseLLMProvider)


def test_openai_provider_message_conversion():
    provider = OpenAIProvider(api_key="sk-mock-key")

    messages = [
        {"sender_type": "customer", "content": "How do I upgrade my plan?"},
        {"sender_type": "agent", "content": "You can upgrade from settings."},
        {"sender_type": "ai", "content": "Here is a quick summary of tiers."},
        {"sender_type": "system", "content": "Ticket marked high priority."},
        {"sender_type": "unknown_type", "content": "Fallback message."},
    ]

    # Without prompt override
    converted = provider._convert_messages(
        conversation_subject="Subscription Tier Question",
        messages=messages,
        prompt_override=None,
    )

    assert len(converted) == 6
    assert converted[0]["role"] == "system"
    assert "Subscription Tier Question" in converted[0]["content"]
    assert converted[1] == {"role": "user", "content": "How do I upgrade my plan?"}
    assert converted[2] == {"role": "assistant", "content": "You can upgrade from settings."}
    assert converted[3] == {"role": "assistant", "content": "Here is a quick summary of tiers."}
    assert converted[4] == {"role": "system", "content": "Ticket marked high priority."}
    assert converted[5] == {"role": "user", "content": "Fallback message."}

    # With prompt override
    converted_override = provider._convert_messages(
        conversation_subject="Billing Question",
        messages=[{"sender_type": "customer", "content": "Refund request"}],
        prompt_override="Escalate immediately if over $1000",
    )
    assert "Escalate immediately if over $1000" in converted_override[0]["content"]


def test_openai_provider_generate_response_mocked():
    # Mock OpenAI client
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "  Thank you for reaching out! We can process your request right away.  "
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)

    result = provider.generate_response(
        conversation_subject="Account Access",
        messages=[{"sender_type": "customer", "content": "Locked out"}],
    )

    assert result == "Thank you for reaching out! We can process your request right away."
    mock_client.chat.completions.create.assert_called_once()
    args, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "Locked out"


def test_openai_provider_missing_api_key():
    with patch.object(settings, "OPENAI_API_KEY", None):
        with pytest.raises(ValueError, match="OPENAI_API_KEY is not configured"):
            OpenAIProvider(api_key=None, client=None)


def test_openai_provider_error_handling():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)

    with pytest.raises(RuntimeError, match="OpenAI provider failed to generate response"):
        provider.generate_response(
            conversation_subject="Error test",
            messages=[],
        )


def test_openai_provider_integration_via_router():
    db: Session = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # Register Owner
        reg = client.post(
            "/auth/register",
            json={
                "company_name": f"OpenAI Corp {suffix}",
                "company_slug": f"openai-corp-{suffix}",
                "full_name": "OpenAI Owner",
                "email": f"openai_owner_{suffix}@example.com",
                "password": password,
            },
        )
        assert reg.status_code == 201
        token = reg.json()["token"]["access_token"]

        # Create Customer
        cust = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": "Customer OpenAI",
                "email": f"cust_oai_{suffix}@example.com",
            },
        )
        assert cust.status_code == 201
        cust_id = cust.json()["id"]

        # Create Conversation
        conv = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "customer_id": cust_id,
                "subject": "Live OpenAI Provider Test",
            },
        )
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        # Add message
        client.post(
            f"/conversations/{conv_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Can I pay via wire transfer?",
                "sender_type": "customer",
            },
        )

        # 1. Test success with OpenAI provider mocked
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Yes, wire transfers are accepted for annual enterprise contracts."
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        mock_provider_instance = OpenAIProvider(api_key="sk-test", client=mock_client)

        with patch("app.ai.commands.process_conversation_ai.get_llm_provider", return_value=mock_provider_instance):
            resp = client.post(
                f"/ai/conversations/{conv_id}/process",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            assert resp.status_code == 200, f"Error: {resp.text}"
            data = resp.json()
            assert data["ai_state"] == "responded"
            assert data["message"]["sender_type"] == "ai"
            assert "wire transfers are accepted" in data["message"]["content"]

        # 2. Test failure handling -> returns 502 Bad Gateway and sets ai_state="failed"
        failing_client = MagicMock()
        failing_client.chat.completions.create.side_effect = Exception("OpenAI API unreachable (503 Service Unavailable)")
        failing_provider_instance = OpenAIProvider(api_key="sk-test", client=failing_client)

        with patch("app.ai.commands.process_conversation_ai.get_llm_provider", return_value=failing_provider_instance):
            fail_resp = client.post(
                f"/ai/conversations/{conv_id}/process",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            assert fail_resp.status_code == 502
            assert "AI provider failed" in fail_resp.text

        # Verify state is updated to "failed" in database
        status_resp = client.get(
            f"/ai/conversations/{conv_id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["ai_state"] == "failed"

    finally:
        db.close()
