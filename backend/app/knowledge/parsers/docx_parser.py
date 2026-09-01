import io
import docx

from app.knowledge.parsers.base import BaseDocumentParser


class DOCXParser(BaseDocumentParser):
    """Parser for DOCX documents using python-docx."""

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        if not file_bytes:
            raise ValueError("Document file is empty")

        try:
            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)

            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)

            full_text = "\n\n".join(paragraphs).strip()
            if not full_text:
                raise ValueError("DOCX document contains no extractable text")

            return full_text

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Failed to parse malformed DOCX document: {str(e)}"
            ) from None
