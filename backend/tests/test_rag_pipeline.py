"""RAG pipeline: extract -> normalize -> chunk -> embed -> pgvector -> hybrid retrieval -> grounded answer."""
import io
import time
import uuid
from unittest.mock import patch

import docx
from fastapi.testclient import TestClient

from app.database.database import SessionLocal
from app.knowledge.ingestion.chunker import chunk_document
from app.knowledge.ingestion.normalize import PAGE_BREAK, normalize_text
from app.knowledge.parsers.docx_parser import DOCXParser
from app.knowledge.parsers.pdf_parser import PDFParser
from app.main import app

client = TestClient(app)
PASSWORD = "SecurePassword123!"

POLICY_TEXT = """Acme Outdoor Help Center

Returns
You can return unworn items within 45 days of delivery. Sale items marked Final Sale cannot be returned. Refunds go to the original payment method within 10 business days.

Shipping
Standard shipping takes 4 to 7 business days and costs $6.95. Orders over $75 ship free. We ship only within the United States.

Warranty
Backpacks carry a lifetime warranty against defects. Damage from misuse is not covered.
"""


# ── helpers ────────────────────────────────────────────────────────
def make_pdf(pages: list[list[str]]) -> bytes:
    """Build a small but valid multi-page text PDF (no external libs)."""
    objs: list[bytes] = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, lines in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        ops = ["BT", "/F1 11 Tf", "72 740 Td", "14 TL"]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def make_docx() -> bytes:
    d = docx.Document()
    d.add_heading("Acme Handbook", level=0)
    d.add_heading("Returns", level=1)
    d.add_paragraph("Items can be returned within 45 days of delivery.")
    d.add_heading("Shipping Rates", level=1)
    table = d.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Standard"
    table.rows[0].cells[1].text = "$6.95"
    table.rows[1].cells[0].text = "Expedited"
    table.rows[1].cells[1].text = "$19.50"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _workspace():
    tag = uuid.uuid4().hex[:8]
    r = client.post("/auth/register", json={
        "company_name": f"RAG {tag}", "company_slug": f"rag-{tag}", "full_name": "Rag Owner",
        "email": f"rag_{tag}@example.com", "password": PASSWORD})
    assert r.status_code == 201, r.text
    tok = client.post("/auth/login", data={"username": f"rag_{tag}@example.com", "password": PASSWORD}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    src = client.post("/knowledge/sources", headers=H, json={"name": "Help", "source_type": "txt"}).json()
    return r.json()["workspace"]["id"], H, src["id"]


def _upload(H, src_id, name: str, data: bytes, ctype="text/plain"):
    return client.post("/knowledge/upload", headers=H, data={"knowledge_source_id": src_id}, files={"file": (name, data, ctype)})


def _wait(H, doc_id, timeout=15):
    for _ in range(timeout * 4):
        d = client.get(f"/knowledge/documents/{doc_id}", headers=H).json()
        if d["status"] not in ("processing", "pending"):
            return d
        time.sleep(0.25)
    return d


def _chat(ws, text):
    r = client.post("/channels/webchat/message", json={
        "workspace_id": ws, "session_id": uuid.uuid4().hex[:10], "content": text, "customer_name": "Sam"})
    assert r.status_code == 200, r.text
    return r.json()


# ── normalization ──────────────────────────────────────────────────
def test_normalize_cleans_extraction_noise():
    raw = "Re-\nfund policy:\nItems can be returned\nwithin 30 days.  ​OK\n\n\n\n• First point\n▪ Second pointﬁnal"
    out = normalize_text(raw)
    assert "Refund policy:" in out or "refund policy:" in out.lower()
    assert "returned within 30 days." in out          # soft-wrapped line re-joined
    assert "​" not in out and " " not in out
    assert "- First point" in out and "- Second point" in out   # bullets unified
    assert "final" in out                              # ligature expanded
    assert "\n\n\n" not in out


def test_normalize_drops_running_headers_and_page_numbers():
    pages = [f"ACME CONFIDENTIAL\nSection {i}\nBody text number {i} is here.\nPage {i}" for i in range(1, 5)]
    out = normalize_text(PAGE_BREAK.join(pages))
    assert "ACME CONFIDENTIAL" not in out
    assert "Page 2" not in out
    assert "Body text number 3 is here." in out
    assert out.count(PAGE_BREAK) == 3


# ── chunking ───────────────────────────────────────────────────────
def test_chunker_respects_sections_and_sentences():
    text = normalize_text(POLICY_TEXT)
    chunks = chunk_document(text, target_chars=200, max_chars=400)
    sections = [c.section for c in chunks]
    assert sections[:1] == ["Returns"] and "Shipping" in sections and "Warranty" in sections
    for c in chunks:
        assert c.content[-1] in ".!?", f"chunk cut mid-sentence: {c.content!r}"
    # sections are never mixed in one chunk
    ret = next(c for c in chunks if c.section == "Returns")
    assert "Standard shipping" not in ret.content
    # the lone title line is not a chunk of its own
    assert all(len(c.content) > 60 for c in chunks)


def test_chunker_long_text_overlap_and_budget():
    sentences = [f"Fact number {i} is stated clearly here." for i in range(60)]
    chunks = chunk_document("Policies\n" + " ".join(sentences), target_chars=300, max_chars=500, overlap_sentences=1)
    assert len(chunks) > 3
    assert all(len(c.content) <= 500 for c in chunks)
    # one sentence of overlap carried into the next chunk
    assert chunks[0].content.split(". ")[-1].strip().rstrip(".") in chunks[1].content


def test_chunker_tracks_pages():
    # a small section that spans a page break is ONE chunk that records both pages
    text = normalize_text("Intro\nFirst page body text for the document.\f" + "Second page body text lives on another page.")
    chunks = chunk_document(text)
    assert len(chunks) == 1 and chunks[0].page == 1 and chunks[0].metadata["page_end"] == 2

    # a long multi-page section splits between blocks and each chunk reports the page it starts on
    pages = ["Details\n" + " ".join(f"Page{p} rule {i} applies to every order." for i in range(60)) for p in (1, 2, 3)]
    chunks = chunk_document(normalize_text("\f".join(pages)), target_chars=700, max_chars=1000)
    assert {c.page for c in chunks} >= {1, 2, 3}
    assert all(len(c.content) <= 1000 for c in chunks)


# ── parsers ────────────────────────────────────────────────────────
def test_pdf_parser_keeps_pages():
    pdf = make_pdf([["Returns policy", "Items may be returned within 45 days."], ["Shipping policy", "Standard shipping costs 6.95 dollars."]])
    text = PDFParser().parse(pdf)
    pages = text.split(PAGE_BREAK)
    assert len(pages) == 2
    assert "45 days" in pages[0] and "6.95" in pages[1]


def test_docx_parser_keeps_headings_and_tables():
    text = DOCXParser().parse(make_docx())
    assert "# Returns" in text and "# Shipping Rates" in text
    assert "Standard | $6.95" in text and "Expedited | $19.50" in text
    assert text.index("# Returns") < text.index("45 days") < text.index("# Shipping Rates")


# ── ingestion over the API ─────────────────────────────────────────
def test_upload_ingests_and_retrieves():
    ws, H, src = _workspace()
    up = _upload(H, src, "help.txt", POLICY_TEXT.encode())
    assert up.status_code == 201, up.text
    assert up.json()["chunk_count"] >= 3
    doc = _wait(H, up.json()["id"])
    assert doc["status"] == "completed" and doc["error_message"] is None

    chunks = client.get(f"/knowledge/documents/{doc['id']}/chunks", headers=H).json()
    assert all(c["has_embedding"] for c in chunks)
    assert {c["metadata_json"]["section"] for c in chunks} >= {"Returns", "Shipping", "Warranty"}

    res = client.post("/knowledge/search", headers=H, json={"query": "standard shipping cost", "top_k": 3}).json()
    assert res["results"][0]["section"] == "Shipping"
    assert res["results"][0]["document_title"] == "help.txt"

    # nothing relevant -> nothing returned (never "the closest random chunk")
    none = client.post("/knowledge/search", headers=H, json={"query": "quantum chromodynamics lattice", "top_k": 3}).json()
    assert none["total"] == 0


def test_pdf_and_docx_uploads_end_to_end():
    ws, H, src = _workspace()
    pdf = _upload(H, src, "rates.pdf", make_pdf([["Shipping rates", "Expedited shipping costs 19.50 dollars."]]), "application/pdf")
    assert pdf.status_code == 201, pdf.text
    dx = _upload(H, src, "handbook.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert dx.status_code == 201, dx.text
    assert _wait(H, pdf.json()["id"])["status"] == "completed"
    assert _wait(H, dx.json()["id"])["status"] == "completed"
    r = client.post("/knowledge/search", headers=H, json={"query": "expedited shipping cost", "top_k": 3}).json()
    assert r["total"] >= 1
    assert any("19.50" in x["content"] for x in r["results"])


def test_embedding_failure_is_reported_not_silent():
    ws, H, src = _workspace()
    with patch("app.embeddings.mock_provider.MockEmbeddingProvider.embed_texts", side_effect=RuntimeError("embedder offline")):
        up = _upload(H, src, "help.txt", POLICY_TEXT.encode())
        assert up.status_code == 201
        doc = _wait(H, up.json()["id"])
    assert doc["status"] == "failed"
    assert "embedder offline" in doc["error_message"]
    # the chunks exist, so keyword search still works, and a later retry can succeed
    assert client.post("/knowledge/search", headers=H, json={"query": "warranty backpack", "top_k": 2}).json()["total"] >= 1
    retry = client.post(f"/knowledge/documents/{doc['id']}/embed", headers=H)
    assert retry.status_code == 200 and retry.json()["status"] == "completed"


def test_delete_and_tenant_isolation_and_reindex():
    ws_a, Ha, src_a = _workspace()
    ws_b, Hb, src_b = _workspace()
    up = _upload(Ha, src_a, "help.txt", POLICY_TEXT.encode())
    doc_id = up.json()["id"]
    _wait(Ha, doc_id)

    # another workspace can neither read, search, nor delete it
    assert client.get(f"/knowledge/documents/{doc_id}", headers=Hb).status_code == 404
    assert client.post("/knowledge/search", headers=Hb, json={"query": "shipping", "top_k": 3}).json()["total"] == 0
    assert client.delete(f"/knowledge/documents/{doc_id}", headers=Hb).status_code == 404

    assert client.post("/knowledge/reindex", headers=Ha).status_code == 202
    assert _wait(Ha, doc_id)["status"] == "completed"

    assert client.delete(f"/knowledge/documents/{doc_id}", headers=Ha).status_code == 204
    assert client.post("/knowledge/search", headers=Ha, json={"query": "shipping", "top_k": 3}).json()["total"] == 0
    db = SessionLocal()
    try:
        from app.knowledge.model import DocumentChunk

        assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).count() == 0
    finally:
        db.close()


# ── answering strictly from the documents ──────────────────────────
def test_answers_come_from_documents_and_cite_sources():
    ws, H, src = _workspace()
    _wait(H, _upload(H, src, "help.txt", POLICY_TEXT.encode()).json()["id"])

    a = _chat(ws, "How long do I have to return an item?")
    assert a["decision"] == "ANSWER"
    assert "45 days" in a["content"]
    assert a["sources"] and a["sources"][0]["section"] == "Returns"
    assert a["sources"][0]["document_title"] == "help.txt"


def test_unanswerable_questions_are_not_invented():
    ws, H, src = _workspace()
    _wait(H, _upload(H, src, "help.txt", POLICY_TEXT.encode()).json()["id"])

    for q in ["What is the capital of France?", "Who founded the company?", "Do you sell tents?"]:
        a = _chat(ws, q)
        assert a["decision"] == "ANSWER" and not a["escalated"], (q, a)
        assert "don't want to guess" in a["content"] or "wrong information" in a["content"]
        assert "bring in the team" in a["content"]
        assert not a["sources"]


def test_no_documents_means_no_answers():
    ws, H, src = _workspace()  # empty knowledge base
    a = _chat(ws, "What is your return policy?")
    assert a["decision"] == "ANSWER" and not a["escalated"] and "bring in the team" in a["content"]
    assert "30-day" not in a["content"] and "hassle-free" not in a["content"].lower()


def test_default_policy_is_never_fabricated():
    from app.ai.tools.registry import tool_registry

    ws, H, src = _workspace()
    db = SessionLocal()
    try:
        res = tool_registry.execute_tool("policy_lookup", db=db, workspace_id=uuid.UUID(ws), arguments={"policy_type": "return"})
    finally:
        db.close()
    assert res.data["found"] is False
    assert "30-day" not in str(res.data)


def test_ungrounded_llm_answer_is_discarded():
    from app.ai.composer import answer_is_grounded

    material = "Items can be returned within 45 days of delivery. Refunds take 10 business days."
    ok, _ = answer_is_grounded("You can return items within 45 days of delivery.", material, "return window?")
    assert ok
    bad, why = answer_is_grounded("You have 90 days to return items and refunds take 3 days.", material, "return window?")
    assert not bad and "unsupported figures" in why
    bad2, _ = answer_is_grounded(
        "Our premium concierge service provides complimentary lifetime consultations with certified specialists worldwide.",
        material, "return window?")
    assert not bad2
