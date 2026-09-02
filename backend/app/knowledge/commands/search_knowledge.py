from sqlalchemy.orm import Session

from app.auth.model import User
from app.embeddings.factory import get_embedding_provider
from app.knowledge.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.knowledge.schema import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)


class SearchKnowledgeCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: KnowledgeSearchRequest,
    ) -> KnowledgeSearchResponse:

        if not data.query or not data.query.strip():
            raise ValueError("Search query cannot be empty")

        cleaned_query = data.query.strip()
        provider = get_embedding_provider()

        # 1. Generate query embedding vector
        try:
            query_vector = provider.embed_text(cleaned_query)
        except Exception as e:
            raise RuntimeError(
                f"Embedding provider failed for query: {str(e)}"
            ) from None

        chunk_repo = DocumentChunkRepository()

        # 2. Strict tenant-isolated vector search
        scored_chunks = chunk_repo.search_similar_chunks(
            db=db,
            workspace_id=current_user.workspace_id,
            query_vector=query_vector,
            top_k=data.top_k,
            knowledge_source_id=data.knowledge_source_id,
        )

        results: list[KnowledgeSearchResult] = []
        for chunk, score in scored_chunks:
            knowledge_source_id = (
                chunk.document.knowledge_source_id if chunk.document else None
            )
            results.append(
                KnowledgeSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    knowledge_source_id=knowledge_source_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    similarity_score=score,
                    metadata_json=chunk.metadata_json,
                )
            )

        return KnowledgeSearchResponse(
            query=cleaned_query,
            results=results,
            total=len(results),
        )
