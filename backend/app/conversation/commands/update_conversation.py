from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.schema import (
    ConversationResponse,
    ConversationUpdateRequest,
)


class UpdateConversationCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
        data: ConversationUpdateRequest,
    ) -> ConversationResponse:

        conversation_repo = ConversationRepository()

        # 1. Tenant boundary check
        conversation = conversation_repo.get_by_id_and_workspace(
            db=db,
            conversation_id=conversation_id,
            workspace_id=current_user.workspace_id,
        )

        if not conversation:
            raise LookupError("Conversation not found")

        # 2. Apply updates
        if data.subject is not None:
            conversation.subject = data.subject.strip()

        if data.status is not None:
            conversation.status = data.status

        db.commit()
        db.refresh(conversation)

        return ConversationResponse.model_validate(conversation)
