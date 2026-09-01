from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.repositories.message_repository import MessageRepository
from app.conversation.schema import MessageResponse


class ListMessagesCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
    ) -> list[MessageResponse]:

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

        # 2. Retrieve messages chronologically
        messages = message_repo.list_by_conversation(
            db=db,
            conversation_id=conversation.id,
        )

        return [MessageResponse.model_validate(msg) for msg in messages]
