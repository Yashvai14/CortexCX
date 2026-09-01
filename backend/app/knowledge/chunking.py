def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Deterministically slice text into ordered overlapping chunks.

    Args:
        text: Raw document text content.
        chunk_size: Maximum character length per chunk (default 500).
        chunk_overlap: Overlapping character count between consecutive chunks
          (default 50).

    Returns:
        List of non-empty string chunks preserving original document order.

    Raises:
        ValueError: If text is empty or chunk parameters are invalid.
    """
    if not text or not text.strip():
        raise ValueError("Document content cannot be empty")

    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than 0")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "Chunk overlap must be non-negative and strictly smaller than chunk size"
        )

    cleaned_text = text.strip()
    text_length = len(cleaned_text)

    # If text is smaller than or equal to chunk size, return single chunk
    if text_length <= chunk_size:
        return [cleaned_text]

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    start = 0

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = cleaned_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start += step

    return chunks
