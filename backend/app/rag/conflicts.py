"""Conflicting-policy detection between retrieved documents.

Two *different* documents that state different values for the same rule ("returns within 7 days" vs "returns within
30 days") must never be blended into one confident answer. Resolution order:

  1. a document explicitly marked authoritative/current in its metadata (`authoritative: true` / `status: current`)
     beats the others;
  2. otherwise the document with the later `effective_date` (ISO date) or higher `version` wins - but only when
     every conflicting document carries that information;
  3. otherwise the conflict is unresolved: the caller must not make a definitive claim and should escalate.

Documents marked outdated/archived/draft/superseded, or past `valid_until`, are excluded earlier (see retrieval).
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.ai.text_utils import retrieval_terms, stem

_DURATION = re.compile(r"\b(\d{1,3})(?:\s*(?:-|to)\s*(\d{1,3}))?\s*(calendar days?|business days?|working days?|days?|hours?|weeks?|months?)\b", re.I)
_RULE_TOPICS = [
    ("return", re.compile(r"\breturn|exchange|replace", re.I)),
    ("refund", re.compile(r"\brefund|money back", re.I)),
    ("delivery", re.compile(r"\bdeliver|shipping|dispatch", re.I)),
    ("cancel", re.compile(r"\bcancel", re.I)),
    ("warranty", re.compile(r"\bwarrant|guarantee", re.I)),
]
_OUTDATED_STATUS = {"outdated", "archived", "superseded", "deprecated", "draft", "expired", "inactive"}
_CURRENT_STATUS = {"current", "active", "authoritative", "official", "latest"}


@dataclass
class ConflictResult:
    conflict: bool = False
    resolved: bool = False
    keep_documents: set[Any] = field(default_factory=set)   # document ids to keep when resolved
    detail: str = ""


def is_outdated(meta: dict | None, today: date | None = None) -> bool:
    """Metadata says this document is no longer in force."""
    m = meta or {}
    if str(m.get("status", "")).lower() in _OUTDATED_STATUS or m.get("outdated") is True or m.get("is_current") is False:
        return True
    until = m.get("valid_until") or m.get("expires_on")
    if until:
        try:
            return date.fromisoformat(str(until)[:10]) < (today or date.today())
        except ValueError:
            return False
    return False


def _facts(text: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """(topic, 'value unit', context terms) for every duration stated next to a rule topic."""
    out = []
    for sentence in re.split(r"(?<=[.!?\n])\s+", text):
        m = _DURATION.search(sentence)
        if not m:
            continue
        topic = next((name for name, pat in _RULE_TOPICS if pat.search(sentence)), None)
        if not topic:
            continue
        unit = m.group(3).lower().rstrip("s")
        unit = "day" if unit in ("calendar day", "day") else unit
        value = f"{m.group(1)}{('-' + m.group(2)) if m.group(2) else ''} {unit}"
        ctx = tuple(sorted({stem(t) for t in retrieval_terms(sentence)} - {stem(m.group(1))}))
        out.append((topic, value, ctx))
    return out


def _authority(meta: dict | None) -> tuple[int, str, str]:
    m = meta or {}
    is_auth = int(m.get("authoritative") is True or str(m.get("status", "")).lower() in _CURRENT_STATUS)
    return is_auth, str(m.get("effective_date") or "")[:10], str(m.get("version") or "")


def detect_conflict(chunks: list[tuple[Any, float]]) -> ConflictResult:
    """`chunks` = [(DocumentChunk, relevance)]. Only compares chunks from different documents."""
    by_doc: dict[Any, list[tuple[str, str, tuple[str, ...]]]] = {}
    meta_of: dict[Any, dict | None] = {}
    title_of: dict[Any, str] = {}
    for chunk, _ in chunks:
        by_doc.setdefault(chunk.document_id, []).extend(_facts(chunk.content))
        doc = getattr(chunk, "document", None)
        meta_of[chunk.document_id] = getattr(doc, "metadata_json", None) if doc else None
        title_of[chunk.document_id] = getattr(doc, "title", "") if doc else ""
    docs = [d for d, f in by_doc.items() if f]
    if len(docs) < 2:
        return ConflictResult()

    clashing: set[Any] = set()
    detail = ""
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            for ta, va, ca in by_doc[a]:
                for tb, vb, cb in by_doc[b]:
                    shared = set(ca) & set(cb)
                    if ta == tb and va != vb and len(shared) >= 3:
                        clashing |= {a, b}
                        detail = f"{title_of.get(a) or a}: {va} vs {title_of.get(b) or b}: {vb} ({ta})"
    if not clashing:
        return ConflictResult()

    ranked = sorted(clashing, key=lambda d: _authority(meta_of.get(d)), reverse=True)
    top, runner_up = _authority(meta_of.get(ranked[0])), _authority(meta_of.get(ranked[1]))
    # resolvable only when the best document is distinguishable by authority marker, effective date or version
    if top != runner_up and (top[0] > runner_up[0] or (top[1] and top[1] > runner_up[1]) or (top[2] and top[2] > runner_up[2])):
        return ConflictResult(conflict=True, resolved=True, keep_documents={ranked[0]}, detail=detail)
    return ConflictResult(conflict=True, resolved=False, detail=detail)
