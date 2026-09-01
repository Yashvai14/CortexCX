from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.knowledge.model import Document


class DocumentRepository(BaseRepository[Document]):

    def __init__(self):
        super().__init__(Document)

    def get_by_id_and_workspace(
        self,
        db: Session,
        document_id: UUID,
        workspace_id: UUID,
    ) -> Document | None:
        return (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            )
            .first()
        )

    def list_by_workspace(
        self,
        db: Session,
        workspace_id: UUID,
        knowledge_source_id: UUID | None = None,
    ) -> list[Document]:
        query = db.query(Document).filter(
            Document.workspace_id == workspace_id
        )
        if knowledge_source_id is not None:
            query = query.filter(
                Document.knowledge_source_id == knowledge_source_id
            )
        return query.order_by(Document.created_at.desc()).all()
