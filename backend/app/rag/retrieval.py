import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.ai.text_utils import GENERAL_STOPWORDS, lexical_coverage, retrieval_terms, stem
from app.core.config import settings
from app.knowledge.model import Document, DocumentChunk
from app.rag.bm25_retriever import BM25Retriever
from app.rag.compressor import ContextCompressor
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.conflicts import is_outdated
from app.rag.query_understanding import QueryPlan, understand


# Sections that describe the document itself rather than the business: rarely what a customer is asking about.
_BOILERPLATE_SECTION = re.compile(
    r"document control|interpretation|version|revision|table of contents|legal notice|disclaimer|glossary|definitions"
    r"|policy update|document information|contact information",
    re.I,
)


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def relevance_score(dense_sim: float | None, coverage: float) -> float:
    """Absolute 0..1 estimate that a passage answers the query (independent of the other candidates).

    - dense_sim is the embedding cosine similarity, rescaled between the model's "unrelated" and "match" levels.
    - coverage is the share of the query's content words found in the passage.
    Either signal can carry a hit (semantic paraphrase with no shared words, or an exact keyword match whose
    embedding is weak), and agreement between them raises confidence.
    """
    floor, ceil = settings.RAG_DENSE_FLOOR, settings.RAG_DENSE_CEIL
    dense = _clip((dense_sim - floor) / (ceil - floor)) if dense_sim is not None else 0.0
    best = max(dense, 0.85 * coverage)
    agree = 0.15 * min(dense, coverage)
    return round(_clip(best + agree), 4)


def _meta(chunk: DocumentChunk) -> dict:
    return chunk.metadata_json or {}


def _title_terms(chunk: DocumentChunk) -> set[str]:
    m = _meta(chunk)
    return {stem(t) for t in retrieval_terms(m.get("section_title") or m.get("section") or "")}


def _near_duplicate(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= 0.85


class RAGRetriever:
    """Two-stage hybrid retrieval.

    Stage 1  dense (pgvector) + BM25 over a conversation-resolved, vocabulary-expanded query -> ~20 candidates.
    Stage 2  rerank on absolute relevance + section-title match, drop boilerplate / superseded / duplicate
             passages, then pick only what the question needs:
               specific question -> the few best passages (<= 5)
               broad question    -> the best passage's whole chapter, in document order (<= 7)
    A passage below the relevance gate is never returned, so an empty result means "the documents do not cover
    this" and the caller must not let the LLM answer from its own knowledge.
    """

    def __init__(self, top_candidates: int | None = None):
        self.hybrid_retriever = HybridRetriever()
        self.bm25_retriever = BM25Retriever()
        self.compressor = ContextCompressor()
        self.top_candidates = top_candidates or settings.RAG_CANDIDATES
        self.last_ranked: list[tuple[DocumentChunk, float, float]] = []

    # ------------------------------------------------------------------ public API
    def retrieve(self, *args: Any, **kwargs: Any) -> list[tuple[DocumentChunk, float]]:
        return self.retrieve_with_plan(*args, **kwargs)[0]

    def retrieve_with_plan(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
        metadata_filter: dict[str, Any] | None = None,
        min_relevance: float | None = None,
        history: list[str] | None = None,
    ) -> tuple[list[tuple[DocumentChunk, float]], QueryPlan]:
        """`history` = this conversation's earlier CUSTOMER messages, oldest first (current message excluded)."""
        plan = understand(query or "", history)
        if not plan.original:
            return [], plan
        gate = settings.RAG_MIN_RELEVANCE if min_relevance is None else min_relevance

        # ---- stage 1: candidates -----------------------------------------------------------------
        try:
            candidates = self.hybrid_retriever.retrieve(
                db=db, workspace_id=workspace_id, query=plan.standalone, lexical_query=plan.lexical,
                top_k=self.top_candidates, knowledge_source_id=knowledge_source_id, metadata_filter=metadata_filter,
            )
        except Exception:
            # Embedding service down: keyword-only retrieval still works.
            candidates = self.bm25_retriever.retrieve(
                db=db, workspace_id=workspace_id, query=plan.lexical, top_k=self.top_candidates,
                knowledge_source_id=knowledge_source_id, metadata_filter=metadata_filter,
            )
            for chunk, _ in candidates:
                chunk.retrieval = {"dense": None, "bm25": None, "rrf": 0.0}

        excluded_docs = self._superseded_documents(db, workspace_id)

        # ---- stage 2: rerank ---------------------------------------------------------------------
        scored: list[tuple[DocumentChunk, float, float]] = []   # (chunk, relevance, rank score)
        for chunk, _rank in candidates:
            if chunk.document_id in excluded_docs:
                continue
            sig = getattr(chunk, "retrieval", {}) or {}
            m = _meta(chunk)
            title = chunk.document.title if chunk.document else ""
            where = f"{title} {m.get('section_path') or m.get('section') or ''}"
            coverage = lexical_coverage(plan.standalone if not plan.resolved_from_history else plan.original, f"{where} {chunk.content}")
            if plan.resolved_from_history:
                coverage = max(coverage, 0.8 * lexical_coverage(plan.standalone, f"{where} {chunk.content}"))
            rel = relevance_score(sig.get("dense"), coverage)

            tt = _title_terms(chunk)
            # Heading match: the customer's subject counts fully; "how long / which payment method" wording only half,
            # so "how many days to return a shirt" prefers "Return Eligibility" over an unrelated "...Timeline".
            boost = (0.4 * (len(tt & plan.subject_terms) + 0.5 * len(tt & plan.qualifier_terms)) / len(tt)) if tt else 0.0
            boiler = 0.5 if _BOILERPLATE_SECTION.search(m.get("section_title") or m.get("section") or "") else 0.0
            # rel saturates at 1.0 for many passages, so the raw signals break ties between close candidates.
            rank = rel + boost + 0.8 * max((sig.get("dense") or 0.0) - 0.4, 0.0) + 0.15 * (sig.get("bm25") or 0.0) - boiler
            chunk.retrieval = {**sig, "coverage": round(coverage, 4), "relevance": rel, "title_boost": round(boost, 3), "rank": round(rank, 4)}
            # A heading that names the topic can rescue a passage whose body words are phrased differently.
            if rel >= gate or (boost >= 0.3 and rel >= 0.2):
                scored.append((chunk, rel, rank))

        scored.sort(key=lambda x: (x[2], (getattr(x[0], "retrieval", {}) or {}).get("rrf", 0.0)), reverse=True)
        unique = self._dedupe(scored)
        self.last_ranked = unique  # full stage-2 ranking, exposed for retrieval evaluation (recall@10 etc.)
        if not unique:
            return [], plan

        # ---- selection: what does this question actually need? ----------------------------------
        if plan.broad:
            picked = self._broad_selection(db, workspace_id, unique, plan, gate)
        else:
            best = unique[0][2]
            cap = max(1, min(top_k, settings.RAG_CONTEXT_MAX_SPECIFIC))
            # Do not pad the context with merely related passages: keep those close to the best one (a second
            # passage is allowed a bit more slack because exceptions and conditions often sit in a neighbour).
            picked = [
                (c, r) for i, (c, r, rk) in enumerate(unique[:cap])
                if i == 0 or rk >= (0.72 if i == 1 else 0.82) * best
            ]
        return self.compressor.compress(picked), plan

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _superseded_documents(db: Session, workspace_id: UUID) -> set[UUID]:
        """Older uploads of the same document (same title) are superseded by the newest one and never retrieved,
        so two versions of one policy cannot be silently blended."""
        rows = (
            db.query(Document.id, Document.title, Document.created_at, Document.metadata_json)
            .filter(Document.workspace_id == workspace_id)
            .all()
        )
        # Documents marked outdated / archived / draft (or past valid_until) are never evidence for an answer.
        outdated = {doc_id for doc_id, _, _, meta in rows if is_outdated(meta if isinstance(meta, dict) else None)}
        docs = [(i, t, c) for i, t, c, _ in rows]
        newest: dict[str, tuple[Any, UUID]] = {}
        for doc_id, title, created in docs:
            if doc_id in outdated:
                continue
            key = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
            if key not in newest or created > newest[key][0]:
                newest[key] = (created, doc_id)
        keep = {doc_id for _, doc_id in newest.values()}
        return {doc_id for doc_id, _, _ in docs if doc_id not in keep}

    @staticmethod
    def _dedupe(scored: list[tuple[DocumentChunk, float, float]]) -> list[tuple[DocumentChunk, float, float]]:
        seen: list[set[str]] = []
        out = []
        for chunk, rel, rank in scored:
            toks = set(retrieval_terms(chunk.content))
            if any(_near_duplicate(toks, s) for s in seen):
                continue  # same rule uploaded/chunked twice must not fill the context with copies
            seen.append(toks)
            out.append((chunk, rel, rank))
        return out

    def _broad_selection(
        self,
        db: Session,
        workspace_id: UUID,
        unique: list[tuple[DocumentChunk, float, float]],
        plan: QueryPlan,
        gate: float,
    ) -> list[tuple[DocumentChunk, float]]:
        """Broad question: take the best passage's whole chapter (its sibling sections), then add strong passages
        from elsewhere (e.g. the "non-returnable products" chapter for a return-policy overview)."""
        limit = settings.RAG_CONTEXT_MAX_BROAD
        lead = unique[0][0]
        lm = _meta(lead)
        parent = lm.get("parent_section") or lm.get("section_title")
        picked: dict[UUID, tuple[DocumentChunk, float]] = {}

        siblings = (
            db.query(DocumentChunk)
            .options(joinedload(DocumentChunk.document))
            .filter(DocumentChunk.workspace_id == workspace_id, DocumentChunk.document_id == lead.document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )
        chapter = [
            c for c in siblings
            if parent and (_meta(c).get("parent_section") == parent or _meta(c).get("section_title") == parent)
            and not _BOILERPLATE_SECTION.search(_meta(c).get("section_title") or "")
        ]
        by_id = {c.id: (r, rk) for c, r, rk in unique}
        subj = plan.subject_terms

        def chapter_rank(c: DocumentChunk) -> float:
            # A section whose HEADING names the subject belongs in an overview ("Refund Processing Timelines" for
            # "what is your refund policy"), whether or not stage 1 happened to surface it; being a stage-1
            # candidate and body overlap only break ties.
            tt = _title_terms(c)
            title_hit = 1.0 if tt & subj else 0.0
            overlap = lexical_coverage(plan.original, f"{_meta(c).get('section_path') or ''} {c.content}")
            return 0.6 * title_hit + 0.3 * overlap + (0.3 if c.id in by_id else 0.0)

        # The lead's whole chapter, best-matching sections first, restored to document order below. Every section
        # of the chapter is wanted when it fits (an overview needs eligibility AND timelines AND methods).
        top_chapter = sorted(chapter, key=chapter_rank, reverse=True)[:limit]
        for c in top_chapter:
            rel = by_id[c.id][0] if c.id in by_id else round(max(gate, 0.4), 4)
            c.retrieval = {**(getattr(c, "retrieval", {}) or {}), "relevance": rel, "via": "chapter"}
            picked[c.id] = (c, rel)
        # Spare slots only: strong passages from OTHER chapters (e.g. exclusions) -- never a summary table that
        # would compete with the detailed section that states the same rule.
        for c, rel, rk in unique:
            if len(picked) >= limit:
                break
            title = _meta(c).get("section_title") or ""
            if (c.id not in picked and rk >= 0.9 and c.document_id == lead.document_id
                    and not re.search(r"summary|overview|purpose|introduction|scope|notice|scenario|example|frequently asked", title, re.I)
                    and (_meta(c).get("section_number") or "")):
                picked[c.id] = (c, rel)
        if not picked:
            # Passages ingested before section metadata existed have no chapter to expand: use the best passages
            # as they are rather than answering "not found" about a document that plainly covers the question.
            return [(c, r) for c, r, _ in unique[: min(limit, 5)]]
        ordered = sorted(picked.values(), key=lambda x: (x[0].document_id != lead.document_id, x[0].chunk_index))
        return ordered[:limit]
