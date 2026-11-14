"""Cache for repeated, context-free knowledge questions.

Many customers ask the same thing ("what is your return policy?"). Re-running retrieval plus an LLM call for each is
slow and costly, so a validated answer is reused - under strict conditions that keep it safe:

  * only standalone knowledge questions: no follow-up, no live store data, no customer-specific memory in the prompt;
  * keyed by the workspace and the question's *meaning-bearing terms* (stemmed, order-independent, stopwords
    removed), so "What is your return policy?" and "your return policy?" share an entry;
  * tied to the knowledge-base version (document count + newest update): uploading, editing or deleting a document
    invalidates every cached answer for that workspace immediately;
  * short TTL (RAG_CACHE_TTL_SECONDS) and a size cap.
"""
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.text_utils import retrieval_terms, stem
from app.core.config import settings
from app.commerce.policy_model import Policy
from app.knowledge.model import Document


@dataclass
class CachedAnswer:
    text: str
    sources: list[dict[str, Any]]
    suggestions: list[str]
    confidence: float
    kb_version: str
    expires: float
    extras: dict[str, Any] = field(default_factory=dict)


def knowledge_version(db: Session, workspace_id: UUID) -> str:
    """Changes whenever a document or a store policy record is added, edited or removed."""
    n, newest = db.query(func.count(Document.id), func.max(Document.updated_at)).filter(
        Document.workspace_id == workspace_id).one()
    pn, pnewest = db.query(func.count(Policy.id), func.max(Policy.updated_at)).filter(
        Policy.workspace_id == workspace_id).one()
    return f"{n}:{newest.isoformat() if newest else '-'}|{pn}:{pnewest.isoformat() if pnewest else '-'}"


def cache_key(workspace_id: UUID, question: str) -> str | None:
    terms = sorted({stem(t) for t in retrieval_terms(question)})
    if len(terms) < 2:
        return None  # too little signal to identify a question safely
    return f"{workspace_id}|{' '.join(terms)}"


class RAGAnswerCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[str, CachedAnswer] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def get(self, key: str | None, kb_version: str) -> CachedAnswer | None:
        if not key or not settings.RAG_CACHE_ENABLED:
            return None
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            if item.expires < time.time() or item.kb_version != kb_version:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return item

    def put(self, key: str | None, kb_version: str, text: str, sources: list, suggestions: list, confidence: float) -> None:
        if not key or not settings.RAG_CACHE_ENABLED or not text:
            return
        with self._lock:
            self._items[key] = CachedAnswer(
                text=text, sources=list(sources), suggestions=list(suggestions), confidence=confidence,
                kb_version=kb_version, expires=time.time() + settings.RAG_CACHE_TTL_SECONDS,
            )
            self._items.move_to_end(key)
            while len(self._items) > settings.RAG_CACHE_MAX_ENTRIES:
                self._items.popitem(last=False)


answer_cache = RAGAnswerCache()
