from app.knowledge.parsers.base import BaseDocumentParser


class TXTParser(BaseDocumentParser):
    """Parser for plain text, markdown, and code files."""

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        if not file_bytes or not file_bytes.strip():
            raise ValueError("Document file is empty")

        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as e:
                raise ValueError(
                    f"Unable to decode text document: {str(e)}"
                ) from None

        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Document file is empty")

        return cleaned
