from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.providers.factory import get_llm_provider
from app.ai.schema import (
    AIProcessConversationRequest,
    AIProcessConversationResponse,
)
from app.auth.model import User
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.repositories.message_repository import MessageRepository
from app.conversation.schema import MessageResponse


def _sender_value(m) -> str:
    return m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type)


class ProcessConversationAICommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
        data: AIProcessConversationRequest | None = None,
    ) -> AIProcessConversationResponse:

        conversation_repo = ConversationRepository()
        message_repo = MessageRepository()

        # 1. Tenant boundary: verify conversation belongs to current user's workspace
        conversation = conversation_repo.get_by_id_and_workspace(
            db=db,
            conversation_id=conversation_id,
            workspace_id=current_user.workspace_id,
        )

        if not conversation:
            raise LookupError("Conversation not found")

        # 2. Check if AI processing is enabled for this conversation
        if not conversation.ai_enabled:
            raise ValueError(
                "AI processing is disabled for this conversation"
            )

        # 3. Transition to processing state
        conversation.ai_state = "processing"
        db.commit()
        db.refresh(conversation)

        # 4. Fetch recent conversation history
        messages = message_repo.list_by_conversation(
            db=db,
            conversation_id=conversation.id,
        )

        # 4b. If there is a customer message to answer, run the FULL cognitive pipeline
        # (memory -> intent -> plan -> tools -> hybrid RAG -> confidence -> answer/escalate),
        # exactly like the Telegram / web-chat channels, instead of a bare LLM call.
        last_customer = next(
            (m for m in reversed(messages) if _sender_value(m) == "customer"),
            None,
        )
        if last_customer is not None:
            from app.ai.orchestrator import ConversationOrchestrator

            result = ConversationOrchestrator.process_turn(
                db=db,
                workspace_id=current_user.workspace_id,
                conversation=conversation,
                customer_message_content=last_customer.content,
                prompt_override=data.prompt_override if data else None,
            )
            db.refresh(conversation)
            ai_message = next(
                (m for m in reversed(message_repo.list_by_conversation(db=db, conversation_id=conversation.id))
                 if _sender_value(m) == "ai"),
                None,
            )
            if ai_message is None:
                # Orchestrator short-circuited (human takeover already active): nothing new was generated.
                raise ValueError(
                    "A human agent already owns this conversation; AI replies are paused until it is returned to AI"
                )
            return AIProcessConversationResponse(
                conversation_id=conversation.id,
                message=MessageResponse.model_validate(ai_message),
                ai_state=conversation.ai_state,
                provider=f"cortex-pipeline ({result.decision.lower()}, confidence {result.confidence_score:.2f})",
            )
        history = [
            {
                "sender_type": (
                    m.sender_type.value
                    if hasattr(m.sender_type, "value")
                    else str(m.sender_type)
                ),
                "content": m.content,
            }
            for m in messages
        ]

        # 5. Invoke LLM provider
        provider = get_llm_provider()
        prompt_override = data.prompt_override if data else None

        try:
            response_content = provider.generate_response(
                conversation_subject=conversation.subject,
                messages=history,
                prompt_override=prompt_override,
            )
        except Exception as e:
            # Set state to failed and commit so state isn't stuck at processing
            conversation.ai_state = "failed"
            db.commit()
            raise RuntimeError(
                f"AI provider failed to generate response: {str(e)}"
            ) from None

        # 6. Create AI message
        ai_message = Message(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.AI,
            sender_user_id=None,
            content=response_content,
        )

        message_repo.add(
            db=db,
            obj=ai_message,
        )

        # 7. Transition to responded state
        conversation.ai_state = "responded"
        db.commit()
        db.refresh(ai_message)
        db.refresh(conversation)

        provider_name = getattr(
            provider, "model_name", provider.__class__.__name__
        )

        return AIProcessConversationResponse(
            conversation_id=conversation.id,
            message=MessageResponse.model_validate(ai_message),
            ai_state=conversation.ai_state,
            provider=provider_name,
        )
