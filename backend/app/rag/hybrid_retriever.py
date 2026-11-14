from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.model import DocumentChunk
from app.rag.bm25_retriever import BM25Retriever
from app.rag.dense_retriever import DenseRetriever
from app.rag.retriever_base import BaseRetriever


class HybridRetriever(BaseRetriever):
    """Dense (pgvector cosine) + BM25 (keyword) retrieval fused with Reciprocal Rank Fusion.

    RRF decides the *order* of candidates. Its score is rank-based (and was previously normalised so the top
    hit was always 1.0), so it says nothing about whether a passage actually answers the question. The raw
    per-retriever signals are therefore attached to each chunk as `chunk.retrieval` for the relevance gate in
    RAGRetriever.
    """

    def __init__(self, rrf_k: int = 60):
        self.dense = DenseRetriever()
        self.bm25 = BM25Retriever()
        self.rrf_k = rrf_k

    def retrieve(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
        metadata_filter: dict[str, Any] | None = None,
        lexical_query: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """`query` drives the dense (meaning) search; `lexical_query` (default: same) drives BM25, so keyword
        search can carry extra vocabulary the dense model does not need."""
        candidate_k = max(top_k * 2, 20)

        dense_results = self.dense.retrieve(
            db=db, workspace_id=workspace_id, query=query, top_k=candidate_k,
            knowledge_source_id=knowledge_source_id, metadata_filter=metadata_filter,
        )
        bm25_results = self.bm25.retrieve(
            db=db, workspace_id=workspace_id, query=lexical_query or query, top_k=candidate_k,
            knowledge_source_id=knowledge_source_id, metadata_filter=metadata_filter,
        )

        rrf_scores: dict[UUID, float] = {}
        chunk_map: dict[UUID, DocumentChunk] = {}
        signals: dict[UUID, dict[str, float | None]] = {}

        for rank, (chunk, sim) in enumerate(dense_results, start=1):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (self.rrf_k + rank)
            signals.setdefault(chunk.id, {"dense": None, "bm25": None})["dense"] = sim

        max_bm25 = max((s for _, s in bm25_results), default=0.0) or 1.0
        for rank, (chunk, score) in enumerate(bm25_results, start=1):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (self.rrf_k + rank)
            signals.setdefault(chunk.id, {"dense": None, "bm25": None})["bm25"] = round(score / max_bm25, 4)

        if not rrf_scores:
            return []

        ordered = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[tuple[DocumentChunk, float]] = []
        for chunk_id, rrf in ordered:
            chunk = chunk_map[chunk_id]
            chunk.retrieval = {**signals[chunk_id], "rrf": round(rrf, 5)}  # transient, not persisted
            results.append((chunk, round(rrf, 5)))
        return results
