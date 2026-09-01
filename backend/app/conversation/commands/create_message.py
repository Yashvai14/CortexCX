from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.repositories.message_repository import MessageRepository
from app.conversation.schema import (
    MessageCreateRequest,
    MessageResponse,
)


class CreateMessageCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
        data: MessageCreateRequest,
    ) -> MessageResponse:

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

        # 2. Origin & sender validation: only AGENT and SYSTEM allowed from internal API
        if data.sender_type == MessageSenderType.CUSTOMER:
            raise ValueError(
                "Customer messages cannot be created through this endpoint"
            )

        if data.sender_type == MessageSenderType.AGENT:
            sender_user_id = current_user.id
        else:
            sender_user_id = None

        # 3. Create message record
        message = Message(
            conversation_id=conversation.id,
            sender_type=data.sender_type,
            sender_user_id=sender_user_id,
            content=data.content.strip(),
        )

        message_repo.add(
            db=db,
            obj=message,
        )

        db.commit()
        db.refresh(message)

        return MessageResponse.model_validate(message)
