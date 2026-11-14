import io

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.knowledge.parsers.base import BaseDocumentParser


class DOCXParser(BaseDocumentParser):
    """DOCX parser that keeps document order, headings, list items and tables (as 'a | b | c' rows)."""

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        if not file_bytes:
            raise ValueError("Document file is empty")

        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            blocks: list[str] = []

            # Walk the body in real order so tables stay next to the text that introduces them.
            for child in doc.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    para = Paragraph(child, doc)
                    text = para.text.strip()
                    if not text:
                        continue
                    style = (para.style.name if para.style is not None else "") or ""
                    if style.lower().startswith("heading") or style.lower() == "title":
                        digits = "".join(c for c in style if c.isdigit())
                        level = min(int(digits), 6) if digits else 1
                        blocks.append(f"{'#' * level} {text}")
                    elif "list" in style.lower():
                        blocks.append(f"- {text}")
                    else:
                        blocks.append(text)
                elif tag == "tbl":
                    table = Table(child, doc)
                    for row in table.rows:
                        cells = []
                        for cell in row.cells:
                            t = cell.text.strip().replace("\n", " ")
                            if t and (not cells or cells[-1] != t):  # merged cells repeat their text
                                cells.append(t)
                        if cells:
                            blocks.append(" | ".join(cells))

            full_text = "\n\n".join(blocks).strip()
            if not full_text:
                raise ValueError("DOCX document contains no extractable text")
            return full_text

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse malformed DOCX document: {str(e)}") from None
