"""Regression tests for the answer-quality problems found in the AI pipeline audit."""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai.intent import IntentClassifier
from app.ai.intent.schema import IntentEnum
from app.ai.text_utils import extract_order_number, keywords
from app.main import app
from scripts.seed_demo import main as seed_workspace

client = TestClient(app)


# ── Pure unit checks (no DB) ───────────────────────────────────────
def test_order_number_extraction_ignores_ordinary_words():
    assert extract_order_number("Where is my order #ORD-1001?") == "ORD-1001"
    assert extract_order_number("my order 12345 hasn't come") == "12345"
    # Previously "please" / "status" were captured as the order number.
    assert extract_order_number("Track my order please") is None
    assert extract_order_number("what is my order status") is None


def test_keywords_drop_filler():
    assert keywords("Do you have the blue hoodie in stock?") == ["blue", "hoodie"]


def test_intent_heuristics():
    c = IntentClassifier._heuristic_classify
    assert c("Does code SAVE20 work?").intent == IntentEnum.COUPON
    assert c("Does code SAVE20 work?").entities["code"] == "SAVE20"
    assert c("How much is the canvas tote?").intent == IntentEnum.PRODUCT_SEARCH
    assert c("my order ORD-9999 never came").intent == IntentEnum.ORDER_STATUS
    assert c("thanks!").entities.get("smalltalk") is True
    assert c("I want to talk to a human").intent == IntentEnum.HUMAN_AGENT
    # 'management' / 'imagent' style substrings must not trigger a human handoff
    assert c("what is the management fee").intent != IntentEnum.HUMAN_AGENT


# ── End-to-end through the real channel + orchestrator ─────────────
def _workspace():
    suffix = uuid.uuid4().hex[:8]
    slug = f"pq-{suffix}"
    r = client.post(
        "/auth/register",
        json={
            "company_name": "Pipeline Store",
            "company_slug": slug,
            "full_name": "Pipe Owner",
            "email": f"pq_{suffix}@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert r.status_code == 201, r.text
    seed_workspace(slug)
    return r.json()["workspace"]["id"]


def _chat(ws: str, text: str, session: str | None = None) -> dict:
    r = client.post(
        "/channels/webchat/message",
        json={
            "workspace_id": ws,
            "session_id": session or uuid.uuid4().hex[:10],
            "content": text,
            "customer_name": "Riya Kapoor",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_grounded_answers_end_to_end():
    ws = _workspace()

    order = _chat(ws, "Where is my order #ORD-1001? My email is aarav@example.com")
    assert order["decision"] == "ANSWER"
    assert "AI Assistant Override" not in order["content"] and "SYSTEM INSTRUCTIONS" not in order["content"]
    assert "ORD-1001" in order["content"] and "BD48271930" in order["content"]
    assert order["content"].startswith("Hi Riya")

    # No order number given: ask for it instead of looking up the word "please".
    ask = _chat(ws, "Track my order please")
    assert "order number" in ask["content"].lower()

    stock = _chat(ws, "Is the black hoodie available?")
    assert "Midnight Black Hoodie" in stock["content"] and "3 left" in stock["content"]

    sold_out = _chat(ws, "Show me running sneakers")
    assert "sold out" in sold_out["content"]

    coupon = _chat(ws, "Does code SUMMER10 work?")
    assert "expired" in coupon["content"].lower()

    policy = _chat(ws, "Do you ship to Canada?")
    assert "Canada" in policy["content"]

    care = _chat(ws, "How do I wash the steel bottle?")
    assert "hand" in care["content"].lower()
    assert care["sources"], "knowledge answers must cite their source"

    hello = _chat(ws, "hi")
    assert hello["decision"] == "ANSWER" and not hello["escalated"] and "help" in hello["content"].lower()


def test_unknown_questions_offer_the_team_instead_of_bluffing_or_escalating():
    ws = _workspace()
    s = uuid.uuid4().hex[:10]
    r = _chat(ws, "what is the meaning of life", s)
    # honest "I don't have that" + an OFFER; nothing is escalated until the customer accepts
    assert r["decision"] == "ANSWER" and r["escalated"] is False and "bring in the team" in r["content"]
    accepted = _chat(ws, "yes please", s)
    assert accepted["decision"] == "ESCALATE" and accepted["escalated"] is True

    human = _chat(ws, "I want to talk to a human")
    assert human["decision"] == "ESCALATE"
    assert "teammate" in human["content"].lower()


def test_agent_assist_draft_is_contextual():
    ws = _workspace()
    session = uuid.uuid4().hex[:10]
    _chat(ws, "I am allergic to nuts. Where is my order #ORD-1001?", session)
    _chat(ws, "I want to talk to a human", session)

    # Read the escalation straight from the DB: summary must carry real context, not a stock sentence.
    from app.database.database import SessionLocal
    from app.escalation.model import HumanEscalation

    db = SessionLocal()
    try:
        esc = db.query(HumanEscalation).filter(HumanEscalation.workspace_id == ws).first()
        assert esc is not None
        assert "ORD-1001" in esc.summary or "order" in esc.summary.lower()
        assert "Why the AI handed off" in esc.summary
        assert esc.suggested_reply != (
            "Hello, I see your request regarding this matter. I am reviewing your account details and will assist you shortly."
        )
    finally:
        db.close()


def test_llm_outage_falls_back_to_grounded_answer_and_is_logged():
    ws = _workspace()
    with patch("app.ai.providers.mock_provider.MockLLMProvider.generate_response", side_effect=RuntimeError("down")):
        r = _chat(ws, "Where is my order #ORD-1001? I'm aarav@example.com")
    # Still a real answer built from the order facts, not "we received your inquiry".
    assert "ORD-1001" in r["content"] and "BD48271930" in r["content"]


# ── Order privacy: lookups require proof the order is the requester's ──
SECRETS = ("BD48271930", "BlueDart", "Classic Blue Hoodie", "1Z999AA10123456784")


def _leaks(text: str) -> bool:
    return any(x in text for x in SECRETS)


def test_order_details_require_identity_check():
    ws = _workspace()

    # 1. Order number alone discloses nothing and asks for the checkout email.
    r = _chat(ws, "Where is my order #ORD-1001?")
    assert not _leaks(r["content"])
    assert "email" in r["content"].lower() and r["decision"] == "ANSWER"

    # 2. A wrong or someone else's email is refused (maya owns ORD-1003, aarav owns ORD-1001).
    wrong = _chat(ws, "Where is my order #ORD-1001? email maya@example.com")
    assert not _leaks(wrong["content"])
    other = _chat(ws, "Status of order ORD-1003, I'm aarav@example.com")
    assert not _leaks(other["content"]) and "UPS" not in other["content"]

    # 3. A nonexistent order gives the same neutral answer as a wrong email (no enumeration).
    ghost = _chat(ws, "Where is my order #ORD-9999? email aarav@example.com")
    mismatch = _chat(ws, "Where is my order #ORD-1003? email aarav@example.com")
    strip = lambda t: t.replace("ORD-9999", "X").replace("ORD-1003", "X")  # noqa: E731
    assert strip(ghost["content"]) == strip(mismatch["content"])

    # 4. The owner's email unlocks it, even when given in a follow-up message of the same chat.
    session = uuid.uuid4().hex[:10]
    first = _chat(ws, "Where is my order #ORD-1001?", session)
    assert not _leaks(first["content"])
    second = _chat(ws, "it's aarav@example.com", session)
    assert second["decision"] == "ANSWER" and "BD48271930" in second["content"]

    ok = _chat(ws, "Where is my order #ORD-1001? aarav@example.com")
    assert "BD48271930" in ok["content"]


def test_order_cancellation_is_also_gated():
    ws = _workspace()
    r = _chat(ws, "Please cancel order ORD-1002")
    assert "Insulated Steel Bottle" not in r["content"]
    assert "email" in r["content"].lower()
    ok = _chat(ws, "Please cancel order ORD-1002, aarav@example.com")
    assert "Insulated Steel Bottle" in ok["content"]


def test_orders_are_isolated_between_workspaces():
    ws_a = _workspace()
    ws_b = _workspace()  # same seeded order numbers and emails, different tenant
    from app.database.database import SessionLocal
    from app.commerce.order_model import Order

    db = SessionLocal()
    try:
        db.query(Order).filter(Order.workspace_id == ws_b, Order.order_number == "ORD-1001").update(
            {Order.tracking_number: "ONLY-IN-B"}
        )
        db.commit()
    finally:
        db.close()
    r = _chat(ws_a, "Where is my order #ORD-1001? aarav@example.com")
    assert "BD48271930" in r["content"] and "ONLY-IN-B" not in r["content"]


# ── LLM-facing safety: fact sheet + output guard ───────────────────
def test_fact_sheet_has_no_ids_and_labels_dates():
    from app.ai.facts import render_facts
    from app.ai.tools.base import ToolResult

    order = ToolResult(tool_name="order_tracking", data={"found": True, "order": {
        "order_number": "ORD-1", "status": "shipped", "total_amount": 59, "currency": "USD",
        "tracking_number": "TRK1", "carrier": "UPS", "estimated_delivery": "2026-11-10T00:00:00+00:00",
        "created_at": "2026-11-08T09:00:00+00:00", "items": [{"product_name": "Hoodie", "quantity": 1}]}})
    product = ToolResult(tool_name="inventory_lookup", data={"found": True, "inventory": {
        "product_id": "dc059bc5-e24a-4298-b98e-69e0338fdb49", "sku": "HOOD-BLK-L",
        "product_name": "Black Hoodie", "quantity_available": 3, "in_stock": True, "low_stock": True}})
    text = render_facts([order, product])
    assert "dc059bc5" not in text and "product_id" not in text
    assert "order placed on 2026-11-08" in text and "estimated delivery 2026-11-10" in text
    assert "shipping/dispatch date is NOT known" in text
    assert "selling fast" in text


def test_output_guard_strips_internal_ids():
    from app.ai.composer import sanitize_reply

    out = sanitize_reply("Yes, the hoodie (product_id: dc059bc5-e24a-4298-b98e-69e0338fdb49, SKU: X) is in stock.")
    assert out == "Yes, the hoodie is in stock."
    assert "dc059bc5" not in sanitize_reply("id dc059bc5-e24a-4298-b98e-69e0338fdb49 here")
