from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.common.repository import BaseRepository
from app.knowledge.model import Document, DocumentChunk


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

    def search_similar_chunks(
        self,
        db: Session,
        workspace_id: UUID,
        query_vector: list[float],
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Nearest chunks by cosine distance, computed inside Postgres by pgvector (HNSW index).

        Returns (chunk, cosine_similarity) pairs, most similar first. Tenant-scoped.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        query = (
            db.query(DocumentChunk, distance.label("distance"))
            .options(joinedload(DocumentChunk.document))
            .filter(
                DocumentChunk.workspace_id == workspace_id,
                DocumentChunk.embedding.isnot(None),
            )
        )
        if knowledge_source_id is not None:
            query = query.join(Document, DocumentChunk.document_id == Document.id).filter(
                Document.knowledge_source_id == knowledge_source_id
            )
        rows = query.order_by(distance).limit(top_k).all()
        return [(chunk, round(1.0 - float(dist), 6)) for chunk, dist in rows]
