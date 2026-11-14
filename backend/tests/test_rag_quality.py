"""RAG answer quality on the THREAD & TREND refund/return policy PDF (the project's labelled evaluation dataset).

Offline tests (mock embeddings + scripted LLM) run everywhere; test_rag_live.py / test_rag_eval_live below run the same
questions against the real embedding model and skip themselves when Ollama is not reachable.
"""
import json
import re
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from tests.test_rag_pipeline import _upload, _wait, _workspace, client  # imports app.main first
from app.ai.answer_format import (
    clean_answer,
    copy_ratio,
    has_artefacts,
    has_unsupported_promise,
    polarity_conflicts,
    table_conflicts,
)
from app.ai.citations import build_sources
from app.core.config import settings
from app.database.database import SessionLocal
from app.knowledge.ingestion.chunker import chunk_document
from app.knowledge.ingestion.normalize import PAGE_BREAK, normalize_text
from app.knowledge.model import Document, DocumentChunk
from app.knowledge.parsers.pdf_parser import PDFParser
from app.rag.query_understanding import understand
from app.rag.retrieval import RAGRetriever

DATA = Path(__file__).parent / "data"
PDF = DATA / "Thread_and_Trend_Refund_Return_Policy.pdf"
SPEC = json.loads((DATA / "rag_eval.json").read_text(encoding="utf8"))


# ── document structure ─────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def pdf_chunks():
    text = normalize_text(PDFParser().parse(PDF.read_bytes()))
    return chunk_document(text, document_title="Refund Policy")


def _by_number(chunks, number):
    return next(c for c in chunks if c.metadata.get("section_number") == number)


def test_pdf_sections_have_real_numbers_pages_and_parents(pdf_chunks):
    c43 = _by_number(pdf_chunks, "4.3")
    assert c43.metadata["section_title"] == "Refund Processing Timelines"
    assert c43.metadata["parent_section"] == "Refund Policy" and c43.metadata["parent_number"] == "4"
    assert c43.metadata["page"] == 9
    assert c43.metadata["section_path"] == "4 Refund Policy > 4.3 Refund Processing Timelines"
    # every numbered section of chapters 1-11 exists exactly once
    numbers = [c.metadata["section_number"] for c in pdf_chunks if re.fullmatch(r"\d+\.\d+", c.metadata.get("section_number") or "")]
    for expected in ("1.1", "2.1", "3.4", "4.1", "4.8", "5.7", "6.7", "7.8", "8.8", "9.7", "11.3"):
        assert numbers.count(expected) == 1, expected


def test_running_page_headers_are_not_sections(pdf_chunks):
    for c in pdf_chunks:
        assert not re.match(r"(?i)^page\s*\d", c.metadata.get("section_title") or ""), c.metadata
        assert "PAGE 2 " not in c.content and "PAGE 4 " not in c.content


def test_lists_and_tables_keep_their_structure(pdf_chunks):
    c41 = _by_number(pdf_chunks, "4.1")
    lines = c41.content.split("\n")
    # numbered conditions on their own lines, never run together
    assert "1. An eligible return is approved." in lines
    assert "2. A defective product is returned and approved for a refund." in lines
    assert not re.search(r"approved\.\s+2\.", c41.content.replace("\n", " ").replace("1. An eligible return is approved. 2.", "X"))
    # a heading is never glued to the previous section's last sentence
    c21 = _by_number(pdf_chunks, "2.1")
    assert "8. The purchase must be verifiable" in c21.content and "2.2 Acceptable" not in c21.content

    c43 = _by_number(pdf_chunks, "4.3")
    assert "| Payment Method | Estimated Refund Timeline |" in c43.content
    assert "| UPI | 3–7 business days |" in c43.content
    # a wrapped bullet is one bullet
    c45 = _by_number(pdf_chunks, "4.5")
    assert "if the order was otherwise correctly fulfilled." in c45.content


def test_faq_and_scenarios_are_one_chunk_each(pdf_chunks):
    faq = [c for c in pdf_chunks if (c.metadata.get("section_number") or "").startswith("Q")]
    scen = [c for c in pdf_chunks if (c.metadata.get("section_number") or "").startswith("Scenario")]
    assert len(faq) == 20 and len(scen) == 15
    q9 = _by_number(pdf_chunks, "Q9")
    assert q9.metadata["section_title"] == "How long does a refund take?"
    assert "initiated within 5 business days" in q9.content and len(q9.content) < 400
    assert max(len(c.content) for c in pdf_chunks) <= settings.RAG_CHUNK_MAX_CHARS


def test_chunks_never_cut_mid_item(pdf_chunks):
    for c in pdf_chunks:
        if not c.metadata.get("section_number"):
            continue          # the cover page is a block of "Key: value" lines
        body = c.content.rstrip()
        assert body[-1] in ".!?:|)\"'", f"{c.metadata['section_number']} ends mid-sentence: {body[-40:]!r}"


# ── query understanding ────────────────────────────────────────────────────────────────────────
def test_followups_are_resolved_from_this_conversation_only():
    p = understand("How long does it take?", ["What is your refund policy?"])
    assert p.resolved_from_history and "refund" in p.standalone.lower()
    # a message that names its own subject is not diluted by earlier turns
    p = understand("What if it was already damaged when delivered?", ["Can I return a shirt?", "What if I wore it once?"])
    assert not p.resolved_from_history and "wore" not in p.standalone
    # no history, nothing to resolve
    assert not understand("How long does it take?", []).resolved_from_history


def test_everyday_wording_is_expanded_to_policy_vocabulary():
    assert "defective" in understand("What happens if my shirt is torn?").lexical
    assert "refund" in understand("How long until my money comes back?").lexical
    assert "incorrect product" in understand("I got the wrong colour").lexical


def test_broad_vs_specific_questions():
    assert understand("What is your return policy?").broad
    assert understand("What are the refund policies?").broad
    assert not understand("How long does a UPI refund take?").broad
    assert not understand("Can I return a washed shirt?").broad


# ── retrieval (offline: keyword search only, the embedding service is not involved) ────────────
@pytest.fixture(scope="module")
def policy_ws():
    ws, H, src = _workspace()
    up = _upload(H, src, PDF.name, PDF.read_bytes(), "application/pdf")
    assert up.status_code == 201, up.text
    assert _wait(H, up.json()["id"])["status"] == "completed"
    return ws, H


def _sections(chunks):
    return [(c.metadata_json or {}).get("section_number") for c, _ in chunks]


def test_retrieval_metrics_offline(policy_ws):
    from scripts.eval_rag import evaluate

    res = evaluate(uuid.UUID(policy_ws[0]), SPEC)["summary"]
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in res.items()})
    assert res["recall@5"] >= 0.90
    assert res["mrr"] >= 0.75
    assert res["context_precision"] >= 0.55
    assert res["duplicate_chunks"] == 0
    assert res["avg_context_chunks"] <= settings.RAG_CONTEXT_MAX_BROAD
    assert res["multi_turn_recall@5"] >= 0.80
    assert res["latency_p95_s"] < 1.0


def test_broad_question_returns_the_whole_chapter_in_order(policy_ws):
    db = SessionLocal()
    try:
        ctx, plan = RAGRetriever().retrieve_with_plan(db, uuid.UUID(policy_ws[0]), "What are the refund policies?", top_k=5)
    finally:
        db.close()
    secs = _sections(ctx)
    assert plan.broad and 4 <= len(secs) <= settings.RAG_CONTEXT_MAX_BROAD
    assert {"4.1", "4.2", "4.3"} <= set(secs)
    chapter4 = [s for s in secs if s and s.startswith("4.")]
    assert chapter4 == sorted(chapter4, key=lambda s: int(s.split(".")[1]))   # document order


def test_specific_question_does_not_pad_the_context(policy_ws):
    db = SessionLocal()
    try:
        ctx, plan = RAGRetriever().retrieve_with_plan(db, uuid.UUID(policy_ws[0]), "How long does a UPI refund take?", top_k=5)
    finally:
        db.close()
    assert not plan.broad and 1 <= len(ctx) <= 4
    assert {"4.3", "Q9"} & set(_sections(ctx))


def test_multi_turn_retrieval_uses_the_customers_earlier_questions(policy_ws):
    db = SessionLocal()
    try:
        r = RAGRetriever()
        ctx, _ = r.retrieve_with_plan(db, uuid.UUID(policy_ws[0]), "How long does it take?", top_k=5,
                                      history=["What is your refund policy?"])
        assert {"4.3", "Q9"} & set(_sections(ctx))
        ctx, _ = r.retrieve_with_plan(db, uuid.UUID(policy_ws[0]), "What if it has already been dispatched?", top_k=5,
                                      history=["Can I cancel my order?"])
        assert {"5.3", "Q11", "Scenario 7"} & set(_sections(ctx))
    finally:
        db.close()


def test_unrelated_and_unsupported_questions_return_nothing(policy_ws):
    db = SessionLocal()
    try:
        for q in ("What is the capital of France?", "Who founded the company?", "quantum chromodynamics lattice"):
            ctx, _ = RAGRetriever().retrieve_with_plan(db, uuid.UUID(policy_ws[0]), q, top_k=5)
            assert ctx == [], (q, _sections(ctx))
    finally:
        db.close()


def test_older_upload_of_the_same_document_is_superseded():
    ws, H, src = _workspace()
    old = _upload(H, src, "policy-v1.txt", b"Refunds\nRefunds are issued within 30 business days of approval for all orders.\n", "text/plain")
    _wait(H, old.json()["id"])
    time.sleep(0.05)
    db = SessionLocal()
    try:   # same title, uploaded later => the newest wins, the old text can never be blended in
        doc = db.query(Document).filter(Document.id == old.json()["id"]).first()
        doc.title = "Refund Policy"
        db.commit()
    finally:
        db.close()
    new = _upload(H, src, "policy-v2.txt", b"Refunds\nRefunds are issued within 5 business days of approval for all orders.\n", "text/plain")
    _wait(H, new.json()["id"])
    db = SessionLocal()
    try:
        d = db.query(Document).filter(Document.id == new.json()["id"]).first()
        d.title = "Refund Policy"
        db.commit()
        ctx, _ = RAGRetriever().retrieve_with_plan(db, uuid.UUID(ws), "How many business days do refunds take?", top_k=5)
    finally:
        db.close()
    text = " ".join(c.content for c, _ in ctx)
    assert "5 business days" in text and "30 business days" not in text


# ── answer formatting & safety ─────────────────────────────────────────────────────────────────
def test_clean_answer_removes_artefacts_and_repairs_markdown():
    raw = ("Answer: Refunds are initiated within **5 business days** [3]. Payment methods: • UPI: 3–7 days • Cards: 5–10 days "
           "(see Section 4.3, Page 9)\n\n\n\nWould you like help with a return?")
    out = clean_answer(raw)
    assert "[3]" not in out and "Section 4.3" not in out and "Page 9" not in out and not out.startswith("Answer")
    assert "**5 business days**" in out
    assert "\n- UPI" in out and "\n- Cards" in out
    assert "\n\n\n" not in out


def test_clean_answer_separates_list_from_paragraph_and_trims_cut_off_text():
    out = clean_answer("You qualify if:\n- The item is unused.\n- Tags are attached.\nPlease contact support if unsure. The team will check the ite")
    assert out.split("\n")[1] == "" or out.split("\n")[0].endswith(":")
    assert "\n\nPlease contact support" in out
    assert out.endswith("unsure.")          # the dangling fragment is dropped, the answer ends on a full stop


def test_raw_pdf_style_text_is_detected_as_an_artefact():
    raw = ("4.1 General Refund Conditions Refunds are issued when a transaction qualifies for a refund under this policy "
           "or applicable law. A refund may be initiated in the following situations: 1. Does that answer your question?")
    assert has_artefacts(raw)
    assert has_artefacts("According to Passage (policy.pdf, 6.2 Manufacturing Defects) the team will check.")
    assert has_artefacts("We do not have an official 'refund' policy record.")
    assert not has_artefacts("Approved refunds are initiated within **5 business days**.\n\n| UPI | 3–7 business days |")


def test_unsupported_promises_are_detected_but_policy_limits_are_not():
    assert has_unsupported_promise("Your refund has been approved and will be credited today.")
    assert has_unsupported_promise("I've processed your cancellation.")
    assert not has_unsupported_promise("Refusing delivery does not automatically guarantee an immediate refund.")
    assert not has_unsupported_promise("If the defect is verified, you may receive a replacement or refund.")


def test_polarity_and_table_misreadings_are_caught():
    material = ("Orders that have already been dispatched cannot normally be cancelled through the standard workflow.\n"
                "| Payment Method | Estimated Refund Timeline |\n|---|---|\n| UPI | 3–7 business days |\n| Credit Card | 5–10 business days |")
    assert polarity_conflicts("You can cancel an order after it has been dispatched through the standard workflow.", material)
    assert not polarity_conflicts("No, you cannot normally cancel an order once it has been dispatched through the standard workflow.", material)
    assert table_conflicts("- Credit Card and UPI: 5–10 business days", material)
    assert not table_conflicts("- UPI: 3–7 business days\n- Credit Card: 5–10 business days", material)


def test_copy_ratio_flags_pasted_passages():
    src = "Customers may request a return within seven calendar days from the date the order is marked as delivered."
    assert copy_ratio(src, src) > 0.9
    assert copy_ratio("You have a week after delivery to ask for a return.", src) < 0.2


# ── citations ──────────────────────────────────────────────────────────────────────────────────
def _chunks_of(ws: str):
    db = SessionLocal()
    try:
        rows = db.query(DocumentChunk).filter(DocumentChunk.workspace_id == ws).order_by(DocumentChunk.chunk_index).all()
        for r in rows:
            _ = r.document.title
        return db, rows
    except Exception:
        db.close()
        raise


def test_citations_name_only_supporting_sections_with_real_metadata(policy_ws):
    db, rows = _chunks_of(policy_ws[0])
    try:
        pool = [(c, 0.8) for c in rows if (c.metadata_json or {}).get("section_number") in {"4.3", "1.2", "11.2", "9.1", "2.1"}]
        answer = ("Approved refunds are generally initiated within **5 business days**. UPI refunds usually take 3–7 business days "
                  "to appear, depending on your payment provider.")
        sources = build_sources(answer, pool, uuid.UUID(policy_ws[0]), cited_hint={1, 2, 3})
    finally:
        db.close()
    assert [s["section_number"] for s in sources] == ["4.3"]
    s = sources[0]
    assert s["section"] == "Refund Processing Timelines" and s["page"] == 9
    assert s["document_title"] == PDF.name and "UPI" in s["excerpt"]
    assert not ({"chunk_id", "id"} & set(s)) and re.fullmatch(r"[0-9a-f]{10}", s["source_id"])


def test_a_chunk_from_another_tenant_is_never_cited(policy_ws):
    db, rows = _chunks_of(policy_ws[0])
    try:
        other_workspace = uuid.uuid4()
        assert build_sources("Approved refunds are initiated within 5 business days after approval.",
                             [(c, 0.9) for c in rows[:40]], other_workspace) == []
    finally:
        db.close()


# ── end to end: scripted LLM through the real pipeline ─────────────────────────────────────────
class ScriptedLLM:
    model_name = "scripted"

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls = 0

    def generate_response(self, **kwargs):
        self.calls += 1
        return self.replies[min(self.calls - 1, len(self.replies) - 1)]


def _chat(ws: str, text: str, session: str | None = None, **extra):
    r = client.post("/channels/webchat/message", json={
        "workspace_id": ws, "session_id": session or uuid.uuid4().hex[:10], "content": text, "customer_name": "Sam Rao", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _ask(ws, question, *llm_replies, session=None, **extra):
    llm = ScriptedLLM(*llm_replies)
    with patch("app.ai.orchestrator.get_llm_provider", return_value=llm):
        return _chat(ws, question, session, **extra), llm


def test_messy_model_output_becomes_a_clean_answer_with_the_right_source(policy_ws):
    raw = ("Answer: Approved refunds are generally initiated within **5 business days** [3]. • Initiated: within 5 business days "
           "• Arrival: another 3–10 business days, depending on the payment method (see Section 4.3)")
    resp, _ = _ask(policy_ws[0], "How long does a UPI refund take?", raw)
    text = resp["content"]
    assert resp["decision"] == "ANSWER"
    assert "[3]" not in text and "Section 4.3" not in text and not text.startswith("Answer")
    assert "\n- Initiated" in text and "\n- Arrival" in text and "**5 business days**" in text
    # the answer is supported by the timelines section (page 9) and/or the matching FAQ entry (page 22)
    assert resp["sources"] and resp["sources"][0]["page"] in {9, 22}
    assert resp["sources"][0]["section"] in {"Refund Processing Timelines", "How long does a refund take?"}
    assert len(resp["sources"]) <= 3
    assert resp["suggestions"] and all(isinstance(s, str) for s in resp["suggestions"])
    assert "chunk_id" not in resp["sources"][0]


def test_pdf_extraction_text_from_the_model_is_replaced_by_a_readable_answer(policy_ws):
    raw = ("4.1 General Refund Conditions Refunds are issued when a transaction qualifies for a refund under this policy or "
           "applicable law. A refund may be initiated in the following situations: 1. Does that answer your question?")
    resp, _ = _ask(policy_ws[0], "What are the refund conditions?", raw)
    text = resp["content"]
    assert "Does that answer your question" not in text and not re.search(r"\b4\.1\s+General", text)
    assert text.count("\n") >= 2                                  # real structure, not one run-on line


def test_invented_promises_never_reach_the_customer(policy_ws):
    promise, _ = _ask(policy_ws[0], "How long does a UPI refund take?", "Your refund has been approved and will be credited today.")
    assert "has been approved" not in promise["content"]


def test_model_that_finds_nothing_hands_off_instead_of_guessing(policy_ws):
    resp, _ = _ask(policy_ws[0], "Do you sell tents?", "NOT_IN_DOCUMENTS")
    assert resp["decision"] == "ANSWER" and not resp["escalated"] and resp["sources"] == []
    assert "bring in the team" in resp["content"]


def test_partial_answers_state_what_the_policy_does_not_specify(policy_ws):
    reply = ("The refund policy does not specify cryptocurrency refunds. Refunds are generally processed to the original "
             "payment method whenever supported by the payment provider. Please contact customer support for confirmation.")
    resp, _ = _ask(policy_ws[0], "Can I get my refund in cryptocurrency?", reply)
    assert resp["decision"] == "ANSWER" and "does not specify cryptocurrency" in resp["content"]
    assert "bitcoin" not in resp["content"].lower()


def test_an_answer_that_pastes_the_passages_gets_one_chance_to_be_rewritten(policy_ws):
    db, rows = _chunks_of(policy_ws[0])
    try:
        # what a model that "summarises" by pasting returns: the passages' body text, without their heading lines
        pasted = "\n\n".join(c.content.split("\n", 2)[2] for c in rows
                             if (c.metadata_json or {}).get("section_number") in {"4.1", "4.2", "4.3", "4.4"})
    finally:
        db.close()
    short = "Refunds are available when a return is approved or an order can't be fulfilled. They're started within **5 business days**."
    resp, llm = _ask(policy_ws[0], "What are the refund policies?", pasted, short)
    assert llm.calls == 2 and len(resp["content"]) < len(pasted)


def test_multi_turn_conversation_keeps_context_and_the_tenant_boundary(policy_ws):
    ws = policy_ws[0]
    session = uuid.uuid4().hex[:10]
    first, _ = _ask(ws, "What is your refund policy?", "Refunds are issued in several situations, for example when an eligible return is approved.", session=session)
    assert first["decision"] == "ANSWER"
    second, _ = _ask(ws, "How long does it take?", "Approved refunds are generally initiated within **5 business days**.", session=session)
    assert second["decision"] == "ANSWER"
    assert any(s["section_number"] in {"4.3", "Q9"} for s in second["sources"])

    # another company's chat never sees this document
    other_ws, _, _ = _workspace()
    other, _ = _ask(other_ws, "What is your refund policy?", "Refunds are issued within 5 business days.")
    assert other["sources"] == [] and not other["escalated"] and "bring in the team" in other["content"]


# ── streaming + retry ──────────────────────────────────────────────────────────────────────────
def _sse(resp_text: str):
    events = []
    for block in resp_text.strip().split("\n\n"):
        ev = re.search(r"^event: (.+)$", block, re.M).group(1)
        data = json.loads(re.search(r"^data: (.+)$", block, re.M).group(1))
        events.append((ev, data))
    return events


def test_stream_reports_real_stages_then_the_validated_answer(policy_ws):
    llm = ScriptedLLM("Approved refunds are generally initiated within **5 business days**.")
    with patch("app.ai.orchestrator.get_llm_provider", return_value=llm):
        r = client.post("/channels/webchat/message/stream", json={
            "workspace_id": policy_ws[0], "session_id": uuid.uuid4().hex[:10],
            "content": "How long does a UPI refund take?", "client_message_id": uuid.uuid4().hex})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = _sse(r.text)
    stages = [d["stage"] for e, d in events if e == "stage"]
    assert stages[0] == "thinking" and "searching" in stages and "writing" in stages
    assert stages.index("searching") < stages.index("writing")
    final = [d for e, d in events if e == "final"][0]
    assert final["decision"] == "ANSWER" and final["sources"]


def test_retrying_a_send_does_not_duplicate_the_customers_message(policy_ws):
    ws = policy_ws[0]
    session, cid = uuid.uuid4().hex[:10], uuid.uuid4().hex
    llm = ScriptedLLM("Approved refunds are generally initiated within **5 business days**.")
    with patch("app.ai.orchestrator.get_llm_provider", return_value=llm):
        first = _chat(ws, "How long does a UPI refund take?", session, client_message_id=cid)
        again = _chat(ws, "How long does a UPI refund take?", session, client_message_id=cid)   # network retry
    assert again["content"] == first["content"] and llm.calls == 1
    from app.conversation.message_model import Message

    db = SessionLocal()
    try:
        n = db.query(Message).filter(Message.conversation_id == first["conversation_id"], Message.content == "How long does a UPI refund take?").count()
    finally:
        db.close()
    assert n == 1


# ── real embeddings (skipped without Ollama) ───────────────────────────────────────────────────
def _ollama_ready() -> bool:
    try:
        tags = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2).json()
        return any(settings.EMBEDDING_MODEL in m.get("name", "") for m in tags.get("models", []))
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_ready(), reason="Ollama embedding model not available")
def test_retrieval_metrics_with_real_embeddings():
    from scripts.eval_rag import evaluate

    old = settings.EMBEDDING_PROVIDER
    settings.EMBEDDING_PROVIDER = "ollama"
    try:
        ws, H, src = _workspace()
        up = _upload(H, src, PDF.name, PDF.read_bytes(), "application/pdf")
        assert _wait(H, up.json()["id"], timeout=120)["status"] == "completed"
        res = evaluate(uuid.UUID(ws), SPEC)["summary"]
    finally:
        settings.EMBEDDING_PROVIDER = old
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in res.items()})
    assert res["recall@5"] >= 0.95 and res["recall@10"] >= 0.95
    assert res["mrr"] >= 0.85
    assert res["context_precision"] >= 0.60
    assert res["duplicate_chunks"] == 0
    assert res["multi_turn_recall@5"] >= 0.90
    assert res["latency_p95_s"] < 1.5
