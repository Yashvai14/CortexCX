import math
from uuid import UUID

from sqlalchemy.orm import Session

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
        """Search workspace chunks by cosine similarity against query vector."""
        query = db.query(DocumentChunk).filter(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.embedding.isnot(None),
        )

        if knowledge_source_id is not None:
            query = query.join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(Document.knowledge_source_id == knowledge_source_id)

        chunks = query.all()
        if not chunks:
            return []

        # Compute cosine similarity for each chunk
        query_mag = math.sqrt(sum(q * q for q in query_vector))
        if query_mag == 0:
            query_mag = 1.0

        scored_chunks: list[tuple[DocumentChunk, float]] = []

        for chunk in chunks:
            if not chunk.embedding:
                continue

            dot_product = sum(
                q * c for q, c in zip(query_vector, chunk.embedding)
            )
            chunk_mag = math.sqrt(sum(c * c for c in chunk.embedding))
            if chunk_mag == 0:
                chunk_mag = 1.0

            similarity = dot_product / (query_mag * chunk_mag)
            scored_chunks.append((chunk, round(similarity, 6)))

        # Order by similarity score descending
        scored_chunks.sort(key=lambda item: item[1], reverse=True)

        return scored_chunks[:top_k]
