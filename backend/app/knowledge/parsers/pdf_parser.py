import io
import re

import pypdf

from app.knowledge.ingestion.normalize import PAGE_BREAK
from app.knowledge.parsers.base import BaseDocumentParser

_COLS = re.compile(r"\s{3,}")
_LIST_MARK = re.compile(r"^(?:\d{1,3}[.)]|[A-Za-z][.)]|[-*•▪●◦‣∙·–])\s")


def _words(text: str) -> int:
    return len(text.split())


def layout_to_text(layout: str) -> str:
    """Turn pypdf's layout-mode text into structured plain text.

    Layout mode keeps what plain extraction destroys: columns of a table stay on one line, list items keep their
    numbering on the same line as their text, and bullets keep their indentation. Here that becomes
      - table rows       -> "| cell | cell |" lines with a header separator (GitHub-style table)
      - indented lines   -> "- item" bullets
      - everything else  -> trimmed text
    """
    lines = layout.replace("\t", " ").replace("\r", "").split("\n")
    out: list[str] = []
    table: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table
        if len(table) >= 2:
            width = max(len(r) for r in table)
            rows = [r + [""] * (width - len(r)) for r in table]
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "---|" * width)
            out.extend("| " + " | ".join(r) + " |" for r in rows[1:])
        else:  # a lone multi-column line is just text, not a table
            for r in table:
                out.append("  ".join(r))
        table = []

    for raw in lines:
        if not raw.strip():
            flush_table()
            out.append("")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        cells = [c.strip() for c in _COLS.split(text) if c.strip()]
        if len(cells) >= 2 and not _LIST_MARK.match(text):
            table.append(cells)
            continue
        flush_table()
        text = re.sub(r"\s{2,}", " ", text)
        prev = out[-1] if out else ""
        wraps_previous = (
            prev.strip()
            and not re.search(r"[.!?:;]$", prev.strip())
            and text[:1].islower()
            and not prev.startswith("|")
        )
        if wraps_previous:
            out[-1] = prev + " " + text  # a sentence wrapped onto the next line (indented or not)
        elif indent >= 3 and not _LIST_MARK.match(text) and not text.endswith(":"):
            out.append(f"- {text}")  # indented, unnumbered line = a bullet
        else:
            out.append(text)
    flush_table()
    return "\n".join(out)


class PDFParser(BaseDocumentParser):
    """PDF parser (pypdf). Pages are separated by a form-feed so chunks can cite their page."""

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        if not file_bytes:
            raise ValueError("Document file is empty")

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))

            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")
                except Exception:
                    raise ValueError("PDF is password protected") from None

            if len(reader.pages) == 0:
                raise ValueError("PDF document contains no pages")

            pages: list[str] = []
            for page in reader.pages:
                plain = (page.extract_text() or "").strip()
                text = plain
                try:
                    layout = page.extract_text(extraction_mode="layout") or ""
                    structured = layout_to_text(layout).strip()
                    # Trust layout mode only if it kept (nearly) all the words plain extraction found.
                    if structured and _words(structured) >= 0.8 * max(_words(plain), 1):
                        text = structured
                except Exception:
                    pass  # older pypdf / odd page: plain text is still usable
                pages.append(text)  # keep empty pages so page numbers stay aligned

            full_text = PAGE_BREAK.join(pages).strip(PAGE_BREAK + "\n ")
            if not full_text.strip():
                raise ValueError(
                    "PDF contains no extractable text (it may be a scanned image; run OCR on it first)"
                )
            return full_text

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse malformed PDF document: {str(e)}") from None
