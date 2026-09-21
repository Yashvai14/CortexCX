from app.knowledge.model import DocumentChunk


class ContextCompressor:
    """Compresses, deduplicates, and condenses retrieved knowledge chunks to optimize prompt space."""

    def __init__(self, max_total_chars: int = 3000):
        self.max_total_chars = max_total_chars

    def compress(
        self,
        chunks: list[tuple[DocumentChunk, float]],
    ) -> list[tuple[DocumentChunk, float]]:
        if not chunks:
            return []

        compressed: list[tuple[DocumentChunk, float]] = []
        seen_sentences: set[str] = set()
        accumulated_chars = 0

        for chunk, score in chunks:
            if accumulated_chars >= self.max_total_chars:
                break

            sentences = chunk.content.split("\n")
            retained_sentences = []

            for s in sentences:
                cleaned = s.strip()
                if not cleaned:
                    continue

                # Deduplicate identical full sentences across chunks
                s_key = cleaned.lower()
                if s_key in seen_sentences:
                    continue

                seen_sentences.add(s_key)
                retained_sentences.append(cleaned)

            if not retained_sentences:
                continue

            cleaned_text = "\n".join(retained_sentences)
            if accumulated_chars + len(cleaned_text) > self.max_total_chars:
                budget_left = max(0, self.max_total_chars - accumulated_chars)
                cleaned_text = cleaned_text[:budget_left] + "..."

            accumulated_chars += len(cleaned_text)
            compressed.append((chunk, score))

        return compressed
