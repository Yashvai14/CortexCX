from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.conversation.message_model import Message


class MessageRepository(BaseRepository[Message]):

    def __init__(self):
        super().__init__(Message)

    def get_by_id(
        self,
        db: Session,
        message_id: UUID,
    ) -> Message | None:
        return (
            db.query(Message)
            .filter(
                Message.id == message_id,
            )
            .first()
        )

    def list_by_conversation(
        self,
        db: Session,
        conversation_id: UUID,
    ) -> list[Message]:
        return (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at.asc())
            .all()
        )
