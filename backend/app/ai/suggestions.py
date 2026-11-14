"""Grounded follow-up suggestions.

Suggestions are built only from the section titles of the SAME document the answer came from: the neighbouring
sections the customer has not been told about yet. They are never generic or invented.
"""
import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.model import DocumentChunk

_SKIP = re.compile(
    r"document control|interpretation|version|revision|table of contents|legal|disclaimer|glossary|definitions"
    r"|policy update|contact information|scope|introduction|purpose|notice|summary|statuses",
    re.I,
)


def _phrase(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip().rstrip("?.")
    low = t.lower()
    if low.startswith(("how ", "what ", "when ", "who ", "can ", "are ", "is ")):
        return t if t.endswith("?") else t + "?"
    return f"Tell me about {low}"


def suggest_followups(db: Session, workspace_id: UUID, used_chunks: list, limit: int = 3) -> list[str]:
    if not used_chunks:
        return []
    lead = used_chunks[0][0]
    lm = lead.metadata_json or {}
    parent = lm.get("parent_section")
    used = {(c.metadata_json or {}).get("section_title") for c, _ in used_chunks}
    used_idx = [c.chunk_index for c, _ in used_chunks]

    rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.workspace_id == workspace_id, DocumentChunk.document_id == lead.document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    pool = []
    for c in rows:
        m = c.metadata_json or {}
        title = m.get("section_title")
        if not title or title in used or _SKIP.search(title) or m.get("continued"):
            continue
        same_chapter = parent is not None and m.get("parent_section") == parent
        distance = min(abs(c.chunk_index - i) for i in used_idx)
        pool.append((0 if same_chapter else 1, distance, c.chunk_index, title))
    pool.sort()
    out, seen = [], set()
    for _, _, _, title in pool:
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append(_phrase(title))
        if len(out) >= limit:
            break
    return out
