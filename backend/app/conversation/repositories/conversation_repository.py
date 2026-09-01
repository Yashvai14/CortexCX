from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.conversation.model import Conversation, ConversationStatus


class ConversationRepository(BaseRepository[Conversation]):

    def __init__(self):
        super().__init__(Conversation)

    def get_by_id_and_workspace(
        self,
        db: Session,
        conversation_id: UUID,
        workspace_id: UUID,
    ) -> Conversation | None:
        return (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.workspace_id == workspace_id,
            )
            .first()
        )

    def list_by_workspace(
        self,
        db: Session,
        workspace_id: UUID,
        customer_id: UUID | None = None,
        status: ConversationStatus | None = None,
    ) -> list[Conversation]:
        query = db.query(Conversation).filter(
            Conversation.workspace_id == workspace_id
        )

        if customer_id is not None:
            query = query.filter(Conversation.customer_id == customer_id)

        if status is not None:
            query = query.filter(Conversation.status == status)

        return query.order_by(Conversation.created_at.desc()).all()

    def update(
        self,
        db: Session,
        conversation: Conversation,
        data: dict,
    ) -> Conversation:
        for key, value in data.items():
            if value is not None and hasattr(conversation, key):
                setattr(conversation, key, value)
        return conversation
