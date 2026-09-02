from uuid import UUID

from sqlalchemy.orm import Session

from app.embeddings.factory import get_embedding_provider
from app.knowledge.model import DocumentChunk
from app.knowledge.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)


class RAGRetriever:
    """Retrieves relevant knowledge chunks for a query within a workspace boundary."""

    def __init__(self):
        self.chunk_repo = DocumentChunkRepository()

    def retrieve(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        if not query or not query.strip():
            return []

        provider = get_embedding_provider()
        try:
            query_vector = provider.embed_text(query.strip())
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate query embedding: {str(e)}"
            ) from None

        return self.chunk_repo.search_similar_chunks(
            db=db,
            workspace_id=workspace_id,
            query_vector=query_vector,
            top_k=top_k,
        )
