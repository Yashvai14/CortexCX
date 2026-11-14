"""Turns a raw model reply into the final customer-facing answer.

    raw reply -> NOT_IN_DOCUMENTS? -> clean & format -> validate (artefacts, promises, groundedness)
              -> (if invalid) readable fallback built from the retrieved passages
              -> citations that really support the text -> grounded follow-up suggestions
"""
import re
from dataclasses import dataclass, field
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.answer_format import (
    clean_answer,
    copy_ratio,
    extractive_answer,
    has_artefacts,
    has_unsupported_promise,
    polarity_conflicts,
    table_conflicts,
)
from app.ai.citations import build_sources
from app.ai.intent.schema import IntentEnum
from app.ai.composer import Grounding, answer_is_grounded, compose_grounded, compose_reply
from app.ai.suggestions import suggest_followups
from app.rag.context import NOT_IN_DOCUMENTS


@dataclass
class FinalAnswer:
    text: str
    sources: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    no_knowledge: bool = False
    fallback: str | None = None      # why the model's text was not used, if it wasn't
    pasted: bool = False             # the answer is (mostly) the passages word for word, not an explanation


def _readable_fallback(grounding: Grounding, chunks: list) -> str | None:
    """Document answer in readable Markdown; store-data answer for tool-only questions."""
    if chunks:
        text = extractive_answer(chunks, broad=grounding.broad)
        if text:
            return text
    return compose_grounded(grounding)


def _finish(text: str, chunks: list, grounding: Grounding, workspace_id: UUID, db: Session, cited: set[int],
            fallback: str | None) -> FinalAnswer:
    sources = build_sources(text, chunks, workspace_id, cited, grounding.broad) if chunks else []
    suggestions = suggest_followups(db, workspace_id, chunks) if sources else []
    return FinalAnswer(text=text, sources=sources, suggestions=suggestions, fallback=fallback)


def finalize_answer(
    raw: str,
    grounding: Grounding,
    chunks: list,
    material: str,
    question: str,
    workspace_id: UUID,
    db: Session,
) -> FinalAnswer:
    if NOT_IN_DOCUMENTS in (raw or "").upper().replace(" ", "_"):
        return FinalAnswer(text="", no_knowledge=True)

    cited = {int(n) for n in re.findall(r"\[(\d{1,2})\]", raw or "")}
    text = clean_answer(raw)

    reason = None
    if not text:
        reason = "empty answer"
    elif has_artefacts(text):
        reason = "document-extraction artefacts in the answer"
    elif has_unsupported_promise(text):
        reason = "promises an outcome the policy does not guarantee"
    else:
        ok, why = answer_is_grounded(text, material, question)
        if not ok:
            reason = why
        else:
            flipped = polarity_conflicts(text, material)
            wrong_rows = table_conflicts(text, material)
            if flipped:
                reason = f"contradicts the policy wording: {flipped[0][:80]!r}"
            elif wrong_rows:
                reason = f"misreads a table row: {wrong_rows[0][:80]!r}"

    pct = re.match(r"only (\d+)%", reason or "")
    if (pct and int(pct.group(1)) < 30 and chunks and not (grounding.entities or {}).get("smalltalk")
            and grounding.intent not in (IntentEnum.ORDER_STATUS, IntentEnum.ORDER_CANCELLATION)):
        # The model answered from its own general knowledge: the documents do not cover this question, so pasting
        # the nearest (unrelated) passage would be worse than saying so.
        logger.warning(f"LLM answer rejected ({reason}); documents do not cover the question. Answer was: {(raw or '')[:200]!r}")
        return FinalAnswer(text="", no_knowledge=True, fallback=reason)

    if reason:
        logger.warning(f"LLM answer rejected ({reason}); using readable fallback. Answer was: {(raw or '')[:300]!r}")
        fb = _readable_fallback(grounding, chunks)
        if fb is None:
            return FinalAnswer(text="", no_knowledge=True, fallback=reason)
        text = clean_answer(fb)
        cited = set()
    result = _finish(text, chunks, grounding, workspace_id, db, cited, reason)
    # A long answer that is mostly the passages pasted back is not an explanation (the caller may ask once more).
    result.pasted = reason is None and len(text) > 700 and copy_ratio(text, material) > 0.55
    return result


def fallback_answer(grounding: Grounding, chunks: list, workspace_id: UUID, db: Session) -> FinalAnswer:
    """The model was unreachable: still answer, from the passages / store facts, never with a generic non-answer."""
    fb = _readable_fallback(grounding, chunks) or compose_reply(grounding)
    return _finish(clean_answer(fb), chunks, grounding, workspace_id, db, set(), "provider unavailable")
