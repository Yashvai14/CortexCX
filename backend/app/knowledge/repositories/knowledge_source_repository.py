from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.knowledge.model import KnowledgeSource


class KnowledgeSourceRepository(BaseRepository[KnowledgeSource]):

    def __init__(self):
        super().__init__(KnowledgeSource)

    def get_by_id_and_workspace(
        self,
        db: Session,
        source_id: UUID,
        workspace_id: UUID,
    ) -> KnowledgeSource | None:
        return (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.id == source_id,
                KnowledgeSource.workspace_id == workspace_id,
            )
            .first()
        )

    def list_by_workspace(
        self,
        db: Session,
        workspace_id: UUID,
    ) -> list[KnowledgeSource]:
        return (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.workspace_id == workspace_id,
            )
            .order_by(KnowledgeSource.created_at.desc())
            .all()
        )
