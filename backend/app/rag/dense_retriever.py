from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.embeddings.factory import get_embedding_provider
from app.knowledge.model import DocumentChunk
from app.knowledge.repositories.document_chunk_repository import DocumentChunkRepository
from app.rag.retriever_base import BaseRetriever


class DenseRetriever(BaseRetriever):
    """Dense vector retriever using embedding cosine similarity."""

    def __init__(self):
        self.chunk_repo = DocumentChunkRepository()

    def retrieve(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not query or not query.strip():
            return []

        provider = get_embedding_provider()
        try:
            query_vector = provider.embed_query(query.strip())
        except Exception as e:
            raise RuntimeError(f"Failed to generate query embedding: {str(e)}") from None

        results = self.chunk_repo.search_similar_chunks(
            db=db,
            workspace_id=workspace_id,
            query_vector=query_vector,
            top_k=top_k,
            knowledge_source_id=knowledge_source_id,
        )

        # Apply optional metadata filtering if specified
        if metadata_filter:
            filtered = []
            for chunk, score in results:
                match = True
                if chunk.metadata_json and isinstance(chunk.metadata_json, dict):
                    for k, v in metadata_filter.items():
                        if chunk.metadata_json.get(k) != v:
                            match = False
                            break
                else:
                    match = False
                if match:
                    filtered.append((chunk, score))
            return filtered

        return results
