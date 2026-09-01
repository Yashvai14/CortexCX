from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.schema import ConversationResponse


class GetConversationCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
    ) -> ConversationResponse:

        conversation_repo = ConversationRepository()

        # Workspace boundary enforced: must match conversation_id AND workspace_id
        conversation = conversation_repo.get_by_id_and_workspace(
            db=db,
            conversation_id=conversation_id,
            workspace_id=current_user.workspace_id,
        )

        if not conversation:
            raise LookupError("Conversation not found")

        return ConversationResponse.model_validate(conversation)
