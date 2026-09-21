from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.knowledge.model import DocumentChunk
from app.rag.bm25_retriever import BM25Retriever
from app.rag.dense_retriever import DenseRetriever
from app.rag.retriever_base import BaseRetriever


class HybridRetriever(BaseRetriever):
    """Hybrid Retriever combining Dense Vector and BM25 Sparse Search via Reciprocal Rank Fusion (RRF)."""

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
    ) -> list[tuple[DocumentChunk, float]]:
        candidate_k = max(top_k * 3, 15)

        # 1. Fetch dense candidates
        dense_results = self.dense.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=query,
            top_k=candidate_k,
            knowledge_source_id=knowledge_source_id,
            metadata_filter=metadata_filter,
        )

        # 2. Fetch BM25 candidates
        bm25_results = self.bm25.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=query,
            top_k=candidate_k,
            knowledge_source_id=knowledge_source_id,
            metadata_filter=metadata_filter,
        )

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_score(d) = sum(1.0 / (k + rank))
        rrf_scores: dict[UUID, float] = {}
        chunk_map: dict[UUID, DocumentChunk] = {}

        # Dense ranking
        for rank, (chunk, _) in enumerate(dense_results, start=1):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (self.rrf_k + rank))

        # BM25 ranking
        for rank, (chunk, _) in enumerate(bm25_results, start=1):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (self.rrf_k + rank))

        if not rrf_scores:
            return []

        # 4. Sort and normalize
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        max_score = sorted_chunks[0][1] if sorted_chunks else 1.0

        fused_results: list[tuple[DocumentChunk, float]] = []
        for chunk_id, raw_rrf in sorted_chunks[:top_k]:
            normalized_score = round(raw_rrf / max_score, 4) if max_score > 0 else 0.0
            fused_results.append((chunk_map[chunk_id], normalized_score))

        return fused_results
