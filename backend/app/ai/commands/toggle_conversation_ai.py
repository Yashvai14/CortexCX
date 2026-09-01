from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.schema import (
    AIConversationStatusResponse,
    AIToggleRequest,
)
from app.auth.model import User
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)


class ToggleConversationAICommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
        data: AIToggleRequest,
    ) -> AIConversationStatusResponse:

        conversation_repo = ConversationRepository()

        # 1. Tenant boundary check
        conversation = conversation_repo.get_by_id_and_workspace(
            db=db,
            conversation_id=conversation_id,
            workspace_id=current_user.workspace_id,
        )

        if not conversation:
            raise LookupError("Conversation not found")

        # 2. Update ai_enabled & state
        conversation.ai_enabled = data.ai_enabled
        if not data.ai_enabled:
            conversation.ai_state = "disabled"
        elif conversation.ai_state == "disabled":
            conversation.ai_state = "idle"

        db.commit()
        db.refresh(conversation)

        # 3. Calculate actual AI message statistics
        ai_messages = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.sender_type == MessageSenderType.AI,
            )
            .order_by(Message.created_at.desc())
            .all()
        )

        total_ai_messages = len(ai_messages)
        last_processed_at = (
            ai_messages[0].created_at if ai_messages else None
        )

        return AIConversationStatusResponse(
            conversation_id=conversation.id,
            ai_enabled=conversation.ai_enabled,
            ai_state=conversation.ai_state,
            total_ai_messages=total_ai_messages,
            last_processed_at=last_processed_at,
        )
