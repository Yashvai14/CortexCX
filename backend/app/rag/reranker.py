import re
from app.knowledge.model import DocumentChunk


class Reranker:
    """Reranks candidate retrieved chunks using lexical coverage, proximity, and query alignment."""

    def rerank(
        self,
        query: str,
        candidates: list[tuple[DocumentChunk, float]],
        top_n: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        if not candidates:
            return []

        query_terms = [t.lower() for t in re.findall(r"\b\w{2,}\b", query) if t.lower() not in ["the", "and", "for", "with", "this", "that"]]
        if not query_terms:
            return candidates[:top_n]

        scored: list[tuple[DocumentChunk, float]] = []

        for chunk, initial_score in candidates:
            content_lower = chunk.content.lower()
            term_hits = sum(1 for t in query_terms if t in content_lower)
            coverage = term_hits / len(query_terms) if query_terms else 0.0

            # Bonus for exact full phrase match
            phrase_bonus = 0.2 if query.lower().strip() in content_lower else 0.0

            # Combined score (50% initial retriever score + 40% query term coverage + 10% phrase bonus)
            rerank_score = (0.50 * initial_score) + (0.40 * coverage) + phrase_bonus
            scored.append((chunk, round(min(1.0, rerank_score), 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]
