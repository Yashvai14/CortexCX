import re
from app.ai.text_utils import keywords, stem
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

        query_terms = [stem(t) for t in keywords(query, 10)]
        if not query_terms:
            return candidates[:top_n]

        scored: list[tuple[DocumentChunk, float]] = []

        for chunk, initial_score in candidates:
            content_lower = chunk.content.lower()
            term_hits = sum(1 for t in query_terms if t in content_lower)
            coverage = term_hits / len(query_terms) if query_terms else 0.0
            # Never surface a chunk sharing no informative term with the query (dense hits with zero
            # lexical overlap are noise, and previously inflated confidence with irrelevant sources).
            if term_hits == 0:
                continue

            # Bonus for exact full phrase match
            phrase_bonus = 0.2 if query.lower().strip() in content_lower else 0.0

            # Combined score (50% initial retriever score + 40% query term coverage + 10% phrase bonus)
            rerank_score = (0.35 * initial_score) + (0.55 * coverage) + phrase_bonus
            scored.append((chunk, round(min(1.0, rerank_score), 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]
