from sqlalchemy.orm import Session

from app.auth.model import User
from app.rag.retrieval import RAGRetriever
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

        # Same retrieval the AI uses to answer: dense (pgvector) + BM25 -> RRF -> relevance gate
        try:
            scored_chunks = RAGRetriever().retrieve(
                db=db,
                workspace_id=current_user.workspace_id,
                query=cleaned_query,
                top_k=data.top_k,
                knowledge_source_id=data.knowledge_source_id,
            )
        except Exception as e:
            raise RuntimeError(f"Retrieval failed: {str(e)}") from None

        results: list[KnowledgeSearchResult] = []
        for chunk, score in scored_chunks:
            sig = getattr(chunk, "retrieval", {}) or {}
            meta = chunk.metadata_json or {}
            results.append(
                KnowledgeSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    knowledge_source_id=chunk.document.knowledge_source_id if chunk.document else None,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    similarity_score=score,
                    metadata_json=chunk.metadata_json,
                    document_title=chunk.document.title if chunk.document else None,
                    section=meta.get("section"),
                    page=meta.get("page"),
                    dense_score=sig.get("dense"),
                    keyword_score=sig.get("bm25"),
                    coverage=sig.get("coverage"),
                )
            )

        return KnowledgeSearchResponse(
            query=cleaned_query,
            results=results,
            total=len(results),
        )
