"""Source attribution: cite only the passages that actually support the answer.

Earlier, every passage that cleared the relevance gate was shown as a source, so a refund-timeline answer could cite
the introduction and the document-control page. Here attribution is computed from the final answer text:

  1. take the distinctive content words of the answer,
  2. greedily pick the passages that cover the most of them that earlier picks did not (set cover),
  3. stop when a passage adds almost nothing new (at most 3 sources, 4 for broad overviews),
  4. give each source its real document name, page, section number/title and the supporting excerpt.

Every value comes from stored chunk metadata, nothing is fabricated; a passage from another tenant is rejected.
"""
import hashlib
import re
from uuid import UUID

from loguru import logger

from app.ai.text_utils import retrieval_terms, stem

_SECONDARY = re.compile(r"frequently asked|faq|scenario|worked example|examples?$|summary|overview", re.I)
_LIST_OR_TABLE = re.compile(r"^\s*(?:[-*]\s+|\d{1,2}[.)]\s+|\|)")


def _terms(text: str) -> set[str]:
    return {stem(t) for t in retrieval_terms(text) if len(t) >= 3}


def source_id(document_id, section_number, page) -> str:
    return hashlib.sha1(f"{document_id}|{section_number}|{page}".encode()).hexdigest()[:10]


def _excerpt(chunk_content: str, answer_terms: set[str], limit: int = 380) -> str:
    """The lines of the passage that best match the answer, in document order, without the heading line."""
    lines = [ln.strip() for ln in chunk_content.split("\n") if ln.strip() and not re.match(r"^\|[-| ]+\|$", ln.strip())]
    if len(lines) > 1 and not _LIST_OR_TABLE.match(lines[0]) and not re.search(r"[.!?]$", lines[0]):
        lines = lines[1:]  # heading line
    scored = [(len(_terms(ln) & answer_terms), i, ln) for i, ln in enumerate(lines)]
    best = sorted(scored, key=lambda x: (-x[0], x[1]))[:3]
    picked = [ln for _, _, ln in sorted(best, key=lambda x: x[1])]
    text = " ".join(re.sub(r"^\s*(?:[-*]|\d{1,2}[.)])\s+", "", ln).strip("| ") for ln in picked)
    text = re.sub(r"\s*\|\s*", " · ", text)
    return (text[: limit - 1].rsplit(" ", 1)[0] + "…") if len(text) > limit else text


def build_sources(
    answer: str,
    chunks: list,
    workspace_id: UUID,
    cited_hint: set[int] | None = None,
    broad: bool = False,
) -> list[dict]:
    """`chunks` = [(DocumentChunk, relevance)] in the order they were numbered in the prompt."""
    if not chunks or not answer.strip():
        return []
    answer_terms = _terms(answer)
    if not answer_terms:
        return []

    cands = []
    for idx, (chunk, rel) in enumerate(chunks, start=1):
        if chunk.workspace_id != workspace_id:   # tenant boundary: never cite another company's document
            logger.error(f"Dropped cross-tenant citation candidate {chunk.id}")
            continue
        support = _terms(chunk.content + " " + ((chunk.metadata_json or {}).get("section_title") or "")) & answer_terms
        cands.append({"idx": idx, "chunk": chunk, "rel": rel, "support": support})

    max_sources = 4 if broad else 3
    covered: set[str] = set()
    chosen: list[dict] = []
    threshold = max(2, int(0.08 * len(answer_terms)))
    hint = cited_hint or set()

    while len(chosen) < max_sources:
        def gain(c: dict) -> float:
            g = len(c["support"] - covered)
            title = (c["chunk"].metadata_json or {}).get("section_title") or ""
            # FAQ / worked-example / summary sections restate rules that live in a dedicated section; cite that
            # authoritative section rather than the (usually much longer) restatement.
            g *= 0.6 if _SECONDARY.search(title) else 1.0
            g += 3.0 * float(c["rel"])                                  # more relevant passage wins close calls
            return g + (1.5 if c["idx"] in hint and g > 0 else 0)       # the model's own citation breaks ties
        remaining = [c for c in cands if c not in chosen]
        if not remaining:
            break
        best = max(remaining, key=gain)
        if len(best["support"] - covered) < threshold and chosen:
            break
        if len(best["support"]) < 2:
            break  # shares (almost) nothing with the answer: not a source
        chosen.append(best)
        covered |= best["support"]

    chosen.sort(key=lambda c: (c["chunk"].document_id, c["chunk"].chunk_index))
    out = []
    for c in chosen:
        ch = c["chunk"]
        m = ch.metadata_json or {}
        doc_title = ch.document.title if ch.document else m.get("document_name") or "Document"
        out.append({
            "source_id": source_id(ch.document_id, m.get("section_number"), m.get("page")),
            "document_title": doc_title,
            "document_name": m.get("document_name") or doc_title,
            "page": m.get("page"),
            "page_end": m.get("page_end"),
            "section_number": m.get("section_number"),
            "section": m.get("section_title") or m.get("section"),
            "section_path": m.get("section_path"),
            "excerpt": _excerpt(ch.content, answer_terms),
            "score": c["rel"],
        })
    return out
