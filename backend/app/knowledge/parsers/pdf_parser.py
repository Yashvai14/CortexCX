import io
import pypdf

from app.knowledge.parsers.base import BaseDocumentParser


class PDFParser(BaseDocumentParser):
    """Parser for PDF documents using pypdf."""

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        if not file_bytes:
            raise ValueError("Document file is empty")

        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)

            if len(reader.pages) == 0:
                raise ValueError("PDF document contains no pages")

            extracted_text_list: list[str] = []
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    extracted_text_list.append(page_text.strip())

            full_text = "\n\n".join(extracted_text_list).strip()
            if not full_text:
                raise ValueError("PDF document contains no extractable text")

            return full_text

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Failed to parse malformed PDF document: {str(e)}"
            ) from None
