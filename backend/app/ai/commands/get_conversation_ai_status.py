from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.schema import AIConversationStatusResponse
from app.auth.model import User
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)


class GetConversationAIStatusCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
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

        # 2. Query real database records for AI messages
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
