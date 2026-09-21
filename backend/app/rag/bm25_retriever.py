import math
import re
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.knowledge.model import Document, DocumentChunk
from app.rag.retriever_base import BaseRetriever


class BM25Retriever(BaseRetriever):
    """BM25 (Best Matching 25) Sparse Keyword Retriever."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-z0-9_-]{2,}\b", text.lower())

    def retrieve(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        q = db.query(DocumentChunk).filter(DocumentChunk.workspace_id == workspace_id)
        if knowledge_source_id:
            q = q.join(Document, DocumentChunk.document_id == Document.id).filter(
                Document.knowledge_source_id == knowledge_source_id
            )

        chunks = q.all()
        if not chunks:
            return []

        # Tokenize corpus and compute document frequencies
        doc_tokens_list: list[list[str]] = []
        doc_lengths: list[int] = []
        df: dict[str, int] = {}

        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            doc_tokens_list.append(tokens)
            doc_lengths.append(len(tokens))
            unique_terms = set(tokens)
            for t in unique_terms:
                df[t] = df.get(t, 0) + 1

        total_docs = len(chunks)
        avg_doc_len = sum(doc_lengths) / total_docs if total_docs > 0 else 1.0

        # Calculate BM25 score for each document
        scored: list[tuple[DocumentChunk, float]] = []

        for idx, chunk in enumerate(chunks):
            # Optional metadata filter
            if metadata_filter and chunk.metadata_json:
                match = all(chunk.metadata_json.get(k) == v for k, v in metadata_filter.items())
                if not match:
                    continue

            tokens = doc_tokens_list[idx]
            d_len = doc_lengths[idx]
            if d_len == 0:
                continue

            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1

            score = 0.0
            for term in query_terms:
                if term not in tf:
                    continue
                term_df = df.get(term, 0)
                # BM25 IDF with smoothing
                idf = math.log((total_docs - term_df + 0.5) / (term_df + 0.5) + 1.0)
                freq = tf[term]
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (d_len / avg_doc_len))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scored.append((chunk, round(score, 6)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
