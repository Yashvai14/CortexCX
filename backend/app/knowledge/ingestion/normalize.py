"""Text normalization applied to every extracted document before chunking.

Extraction (PDF/DOCX/HTML/TXT) produces messy text: hard-wrapped lines, hyphenated line breaks, repeated page
headers/footers, ligatures, odd bullets, stray control characters. Normalizing once, here, means chunking and
retrieval work on clean prose and the same document always yields the same chunks.

Page boundaries are kept as form-feed characters (\\f) so chunks can cite their page.
"""
import re
import unicodedata
from collections import Counter

PAGE_BREAK = "\f"

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_BULLETS = re.compile(r"^[ \t]*[•▪●◦‣∙·*–—][ \t]+", re.M)
_PAGE_NUMBER_LINE = re.compile(r"^\s*(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?\s*$|^\s*[-–—]\s*\d{1,4}\s*[-–—]\s*$", re.I)
_SENTENCE_END = re.compile(r"[.!?:;\"')\]]$")
_LIST_OR_HEADING = re.compile(r"^(?:[-*]\s|\d+[.)]\s|#{1,6}\s|[A-Z][A-Z0-9 &/,\-]{3,}$)")


def _drop_repeated_page_furniture(pages: list[str]) -> list[str]:
    """Remove short lines that repeat on most pages (running headers/footers) and bare page numbers."""
    if len(pages) >= 3:
        counts: Counter[str] = Counter()
        for page in pages:
            for line in {ln.strip() for ln in page.splitlines() if 0 < len(ln.strip()) <= 90}:
                counts[line] += 1
        threshold = max(3, int(len(pages) * 0.6))
        furniture = {line for line, n in counts.items() if n >= threshold}
    else:
        furniture = set()

    cleaned = []
    for page in pages:
        lines = [ln for ln in page.splitlines() if ln.strip() not in furniture and not _PAGE_NUMBER_LINE.match(ln)]
        cleaned.append("\n".join(lines))
    return cleaned


def _normalize_page(page: str) -> str:
    # Re-join words broken by end-of-line hyphenation: "refund-\nable" -> "refundable"
    page = re.sub(r"([a-z])-\n([a-z])", r"\1\2", page)

    lines = [ln.rstrip() for ln in page.split("\n")]
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        # Soft-wrapped line: previous line is mid-sentence and this one continues in lowercase.
        if (
            out
            and out[-1]
            and not _SENTENCE_END.search(out[-1])
            and not _LIST_OR_HEADING.match(out[-1])
            and not _LIST_OR_HEADING.match(stripped)
            and stripped[0].islower()
        ):
            out[-1] = out[-1] + " " + stripped
        else:
            out.append(stripped)

    text = "\n".join(out)
    text = _BULLETS.sub("- ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_text(raw: str) -> str:
    """Return clean, deterministic text. Empty input yields an empty string."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)  # ligatures (ﬁ -> fi), full-width chars, nbsp variants
    text = text.translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", "", text)  # control chars (keeps \t \n \f)
    text = text.replace("\t", " ")  # some PDFs put a tab between every word; tabs wreck chunking, search and display

    pages = text.split(PAGE_BREAK)
    pages = _drop_repeated_page_furniture(pages)
    pages = [_normalize_page(p) for p in pages]
    # Keep page structure only when there is more than one non-empty page.
    non_empty = [p for p in pages if p]
    return PAGE_BREAK.join(pages if len(non_empty) > 1 else non_empty).strip(PAGE_BREAK + "\n ")
