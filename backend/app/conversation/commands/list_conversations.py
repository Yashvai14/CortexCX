from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.model import ConversationStatus
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.schema import ConversationResponse


class ListConversationsCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        customer_id: UUID | None = None,
        status: ConversationStatus | None = None,
    ) -> list[ConversationResponse]:

        conversation_repo = ConversationRepository()

        # Workspace boundary enforced automatically
        conversations = conversation_repo.list_by_workspace(
            db=db,
            workspace_id=current_user.workspace_id,
            customer_id=customer_id,
            status=status,
        )

        return [
            ConversationResponse.model_validate(conv) for conv in conversations
        ]
