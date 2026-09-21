from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.knowledge.model import DocumentChunk
from app.rag.bm25_retriever import BM25Retriever
from app.rag.compressor import ContextCompressor
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import Reranker


class RAGRetriever:
    """Full-featured Hybrid RAG Retrieval Engine with BM25 + Dense Fusion, Reranking, and Compression."""

    def __init__(self, top_candidates: int = 15):
        self.hybrid_retriever = HybridRetriever()
        self.bm25_retriever = BM25Retriever()
        self.reranker = Reranker()
        self.compressor = ContextCompressor()
        self.top_candidates = top_candidates

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

        cleaned_query = query.strip()

        # 1. Hybrid Retrieval (Dense Vector + BM25 Sparse Keyword)
        candidates: list[tuple[DocumentChunk, float]] = []
        try:
            candidates = self.hybrid_retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=cleaned_query,
                top_k=max(top_k * 2, self.top_candidates),
                knowledge_source_id=knowledge_source_id,
                metadata_filter=metadata_filter,
            )
        except Exception:
            # Resilient fallback to pure BM25 keyword search if vector embeddings fail
            candidates = self.bm25_retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=cleaned_query,
                top_k=top_k * 2,
                knowledge_source_id=knowledge_source_id,
                metadata_filter=metadata_filter,
            )

        if not candidates:
            return []

        # 2. Cross-Encoder / Semantic Reranking
        reranked = self.reranker.rerank(
            query=cleaned_query,
            candidates=candidates,
            top_n=top_k,
        )

        # 3. Context Compression & Deduplication
        compressed = self.compressor.compress(reranked)

        return compressed
