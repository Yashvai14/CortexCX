from uuid import UUID

from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.knowledge.model import DocumentChunk


class DocumentChunkRepository(BaseRepository[DocumentChunk]):

    def __init__(self):
        super().__init__(DocumentChunk)

    def list_by_document_and_workspace(
        self,
        db: Session,
        document_id: UUID,
        workspace_id: UUID,
    ) -> list[DocumentChunk]:
        return (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.workspace_id == workspace_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

    def create_chunks_bulk(
        self,
        db: Session,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        db.add_all(chunks)
        db.flush()
        return chunks
