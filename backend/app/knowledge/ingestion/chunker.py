"""Hierarchical, structure-preserving chunking.

Pipeline: normalized text -> typed blocks with a heading hierarchy (structure.py) -> section units -> chunks.

  * A *section unit* is a heading (chapter or numbered section) with everything under it until the next one.
  * A unit that fits is kept whole as ONE chunk: its heading line, paragraphs, lists and tables, with line breaks
    intact. Nothing is flattened into a single run-on line.
  * A unit that is too large is split only between blocks (list items / table rows / sentences as a last resort);
    each continuation repeats the heading, and a little context is carried over.
  * Every chunk records where it came from (section number, title, parent chapter, section path, pages) read from
    the document itself, so citations can never name a heading the document does not contain.

Sizes are in characters (about 4 per token): target 1800 (~450 tokens), hard max 2800 (~700 tokens).
"""
import re
from dataclasses import dataclass, field

from app.core.config import settings
from app.knowledge.ingestion.structure import Block, Heading, SectionPath, parse_blocks

_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")


@dataclass
class ChunkSpec:
    content: str
    section: str | None = None          # section title (no number), kept for display / ranking
    page: int | None = None
    metadata: dict = field(default_factory=dict)


def _split_sentences(paragraph: str) -> list[str]:
    parts: list[str] = []
    for line in paragraph.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(("- ", "|")) or re.match(r"^\d{1,3}[.)]\s", line):
            parts.append(line)  # list items and table rows stay whole
        else:
            parts.extend(s.strip() for s in _SENT_SPLIT.split(line) if s.strip())
    return parts


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    words, pieces, cur = sentence.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            pieces.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def _atoms(block: Block, max_chars: int) -> list[str]:
    """Smallest pieces of a block that may be separated: paragraphs/lists by line, tables by row (header kept)."""
    if block.kind == "table":
        rows = block.text.split("\n")
        if len(block.text) <= max_chars or len(rows) <= 3:
            return [block.text]
        head, body = rows[:2], rows[2:]
        out, cur = [], list(head)
        for r in body:
            if len("\n".join(cur + [r])) > max_chars and len(cur) > 2:
                out.append("\n".join(cur))
                cur = list(head)
            cur.append(r)
        out.append("\n".join(cur))
        return out
    if len(block.text) <= max_chars:
        return [block.text]
    out = []
    for piece in _split_sentences(block.text):
        out.extend(_hard_split(piece, max_chars) if len(piece) > max_chars else [piece])
    return out


def _heading_line(h: Heading | None) -> str:
    if not h:
        return ""
    return f"{h.number} {h.title}".strip() if h.number else h.title


def chunk_document(
    text: str,
    target_chars: int | None = None,
    max_chars: int | None = None,
    overlap_sentences: int | None = None,
    document_title: str | None = None,
) -> list[ChunkSpec]:
    target = target_chars or settings.RAG_CHUNK_TARGET_CHARS
    hard_max = max_chars or settings.RAG_CHUNK_MAX_CHARS
    overlap = settings.RAG_CHUNK_OVERLAP_SENTENCES if overlap_sentences is None else overlap_sentences
    if not text or not text.strip():
        return []

    blocks = parse_blocks(text)
    chunks: list[ChunkSpec] = []

    # ---- group blocks into section units ---------------------------------------------------------
    stack: list[Heading] = []
    units: list[dict] = []
    cur: dict | None = None

    def open_unit(heading: Heading | None, page: int) -> dict:
        return {"heading": heading, "chain": list(stack), "blocks": [], "page": page, "page_end": page}

    for b in blocks:
        if b.kind == "heading" and b.heading is not None:
            h = b.heading
            while stack and stack[-1].level >= h.level:
                stack.pop()
            stack.append(h)
            # Chapters and numbered/plain sections start a new unit; deeper subheads stay inside their parent
            # unit (their line is kept in the text) so a section is not shredded into tiny pieces.
            if h.level <= 2 or h.entry or cur is None or not (h.number and len(h.number) == 1 and h.number.isalpha()):
                if cur is not None:
                    units.append(cur)
                cur = open_unit(h, b.page)
                continue
        if cur is None:
            cur = open_unit(None, b.page)
        cur["blocks"].append(b if b.kind != "heading" else Block("para", b.text, b.page))
        cur["page_end"] = b.page
    if cur is not None:
        units.append(cur)

    # ---- turn each unit into one or more chunks --------------------------------------------------
    for unit in units:
        heading: Heading | None = unit["heading"]
        chain: list[Heading] = unit["chain"]
        head_line = _heading_line(heading)
        body_blocks: list[Block] = unit["blocks"]
        if heading is not None and not body_blocks and heading.level == 1:
            continue  # a chapter title with nothing under it: it only supplies context to its sections

        parent = chain[0] if len(chain) > 1 else None
        if heading is not None and heading.level == 1:
            parent = None
        if heading is not None and heading.entry and len(chain) > 2:
            parent = chain[-2]   # an FAQ entry belongs to its FAQ section ("Frequently Asked Questions")
        path = " > ".join(_heading_line(h) for h in chain) if chain else (document_title or "")

        def make(body: str, first_page: int, last_page: int, continued: bool) -> None:
            body = body.strip()
            if not body:
                return
            title_line = head_line + (" (continued)" if continued and head_line else "")
            content = f"{title_line}\n\n{body}".strip() if head_line else body
            meta = {
                "section": heading.title if heading else None,
                "section_number": heading.number if heading else None,
                "section_title": heading.title if heading else None,
                "parent_section": parent.title if parent else None,
                "parent_number": parent.number if parent else None,
                "section_path": path or None,
                "entry": bool(heading and heading.entry),
                "anchor_section": next((h.number for h in reversed(chain[:-1]) if h.number and h.number[0].isdigit()), None)
                if heading and heading.entry else None,
                "page": first_page,
                "page_end": last_page,
                "chars": len(content),
                "continued": continued,
            }
            chunks.append(ChunkSpec(content=content, section=meta["section"], page=first_page, metadata=meta))

        # (text, page, block index, was-split-sentence?) -- pieces of ONE split paragraph are re-joined with a
        # space, list items / table rows with a newline, and separate blocks with a blank line.
        atoms: list[tuple[str, int, int, str]] = []
        for bi, b in enumerate(body_blocks):
            pieces = _atoms(b, hard_max - len(head_line) - 20)
            kind = "block" if len(pieces) == 1 else ("sent" if b.kind == "para" else "line")
            for a in pieces:
                atoms.append((a, b.page, bi, kind))

        def join(items: list[tuple[str, int, int, str]]) -> str:
            out = ""
            for i, (text, _pg, bi, kind) in enumerate(items):
                if i == 0:
                    out = text
                    continue
                prev = items[i - 1]
                if prev[2] == bi and kind == "sent":
                    out += " " + text
                elif prev[2] == bi and kind == "line":
                    out += "\n" + text
                else:
                    out += "\n\n" + text
            return out

        total = len(head_line) + sum(len(a[0]) + 2 for a in atoms)
        if total <= hard_max:
            make(join(atoms), unit["page"], unit["page_end"], False)
            continue

        buf: list[tuple[str, int, int, str]] = []
        size = len(head_line)
        started = False
        carried = 0
        for atom in atoms:
            if buf and size + len(atom[0]) + 2 > target and len(buf) > carried:
                make(join(buf), buf[0][1], buf[-1][1], started)
                started = True
                keep = buf[-overlap:] if overlap > 0 and len(buf[-1][0]) <= 400 else []
                buf = list(keep)
                carried = len(keep)
                size = len(head_line) + sum(len(x[0]) + 2 for x in buf)
            buf.append(atom)
            size += len(atom[0]) + 2
        if len(buf) > carried:
            make(join(buf), buf[0][1], buf[-1][1], started)

    # A lone title/cover line before the first heading is not a useful passage by itself.
    if len(chunks) > 1 and chunks[0].section is None and len(chunks[0].content) < 60:
        chunks = chunks[1:]
    return chunks
