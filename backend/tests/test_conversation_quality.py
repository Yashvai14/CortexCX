"""Behavioural regression tests for the failures seen in the Telegram screenshots.

Root cause being guarded: one unclaimed escalation used to lock the whole conversation, so every later message
("Hi", "I didn't say anything") returned the same "passed this on to my teammate" line without being routed.
"""
import itertools
import threading
import uuid
from unittest.mock import patch
from uuid import UUID

import pytest

from tests.test_hybrid_router import _chat, _Explode, _workspace  # imports app.main first (resolves import order)
from app.ai.handoff import INTERNAL_ERROR, OFFER_MARKER
from app.ai.outbound import enforce_outbound
from app.ai.routing import IntentRouter, Route, RouterIntent
from app.channels.idempotency import ChatLocks, UpdateDeduper, deduper
from app.channels.telegram_adapter import TelegramAdapter
from app.database.database import SessionLocal
from app.escalation.model import EscalationStatus, HumanEscalation

_ids = itertools.count(10_000)


@pytest.fixture(scope="module")
def ws():
    return _workspace()


class _Boom:
    """Fails the test if an escalation is created."""
    def __call__(self, *a, **k):
        raise AssertionError("no escalation may be created for this message")


def _escalations(conversation_id) -> list[HumanEscalation]:
    db = SessionLocal()
    try:
        return db.query(HumanEscalation).filter(HumanEscalation.conversation_id == UUID(str(conversation_id))).all()
    finally:
        db.close()


def _no_rag_no_escalation():
    return patch("app.ai.orchestrator.RAGRetriever", _Explode), patch(
        "app.ai.orchestrator.ticket_auto.create_for_escalation", _Boom())


def _quiet(text, session):
    """Send a message that must reach neither retrieval nor escalation."""
    a, b = _no_rag_no_escalation()
    with a, b:
        r = _chat(ws_id(), text, session)
    assert r["decision"] == "ANSWER" and not r["escalated"] and r["sources"] == [], (text, r)
    return r


_WS: dict[str, str] = {}


def ws_id() -> str:
    return _WS["id"]


@pytest.fixture(autouse=True)
def _bind_ws(ws):
    _WS["id"] = ws


# ══════════════════════ the screenshot failures ══════════════════════════════════════════════
def test_1_greeting_is_direct_no_rag_no_escalation():
    d = IntentRouter.route_by_rules("Hi")
    assert d.route == Route.DIRECT and d.intent == RouterIntent.GREETING
    r = _quiet("Hi", uuid.uuid4().hex[:10])
    assert "passed this on" not in r["content"] and "?" in r["content"]


def test_2_i_didnt_say_anything_is_a_correction_not_a_handoff():
    s = uuid.uuid4().hex[:10]
    _quiet("Hi", s)
    d = IntentRouter.route_by_rules("I didn't say anything")
    assert d.route == Route.DIRECT and d.intent == RouterIntent.CORRECTION
    r = _quiet("I didn't say anything", s)
    assert "sorry" in r["content"].lower() and "passed this on" not in r["content"]


def test_3_explicit_human_request_escalates_and_is_recorded():
    s = uuid.uuid4().hex[:10]
    r = _chat(ws_id(), "I want to speak to a human", s)
    assert r["decision"] == "ESCALATE" and r["escalated"]
    assert len(_escalations(r["conversation_id"])) == 1       # announced only AFTER the request exists
    for text in ("Can I talk to someone?", "Connect me with customer support", "I want to speak to your manager",
                 "Please let your support team call me"):
        assert IntentRouter.route_by_rules(text).route == Route.ESCALATE, text


def test_4_return_policy_uses_rag():
    from app.ai import orchestrator as orch
    calls = []
    real = orch.RAGRetriever.retrieve_with_plan

    def spy(self, *a, **k):
        calls.append(1)
        return real(self, *a, **k)
    with patch.object(orch.RAGRetriever, "retrieve_with_plan", spy):
        r = _chat(ws_id(), "What is your return policy?")
    assert len(calls) == 1 and r["decision"] == "ANSWER"
    assert IntentRouter.route_by_rules("Hi, I want to know your return policy").route == Route.RAG


def test_5_follow_up_question_keeps_the_previous_topic():
    s = uuid.uuid4().hex[:10]
    _chat(ws_id(), "What is your return policy?", s)
    from app.ai import orchestrator as orch
    seen = {}
    real = orch.RAGRetriever.retrieve_with_plan

    def spy(self, *a, **k):
        seen["history"] = k.get("history")
        return real(self, *a, **k)
    with patch.object(orch.RAGRetriever, "retrieve_with_plan", spy):
        _chat(ws_id(), "What about damaged products?", s)
    assert seen["history"] and "return policy" in " ".join(seen["history"]).lower()


def test_5b_hi_then_return_my_shirt_switches_to_rag():
    s = uuid.uuid4().hex[:10]
    _quiet("Hi", s)
    from app.ai import orchestrator as orch
    calls = []
    real = orch.RAGRetriever.retrieve_with_plan

    def spy(self, *a, **k):
        calls.append(1)
        return real(self, *a, **k)
    with patch.object(orch.RAGRetriever, "retrieve_with_plan", spy):
        _chat(ws_id(), "I want to return my shirt", s)
    assert calls


def test_6_thank_you_is_direct():
    r = _quiet("Thank you.", uuid.uuid4().hex[:10])
    assert "welcome" in r["content"].lower() or "glad" in r["content"].lower() or "anytime" in r["content"].lower()


def test_7_where_is_my_order_uses_the_business_tool_path_and_asks_for_details_not_a_human():
    assert IntentRouter.route_by_rules("Where is my order?").route == Route.TOOLS
    a, b = _no_rag_no_escalation()
    with a, b:
        r = _chat(ws_id(), "Where is my order?")
    assert not r["escalated"] and "order number" in r["content"].lower()


def test_8_refund_request_vs_refund_policy():
    # a policy QUESTION -> knowledge
    for q in ("Can I get a refund?", "What is your refund policy?", "How long does a refund take?"):
        assert IntentRouter.route_by_rules(q).route == Route.RAG, q
    # an actual REQUEST -> the order workflow, which needs approval from a person: asks, then OFFERS the team
    assert IntentRouter.route_by_rules("I want a refund").route == Route.TOOLS
    s = uuid.uuid4().hex[:10]
    a, b = _no_rag_no_escalation()
    with a, b:
        ask = _chat(ws_id(), "I want a refund", s)
        assert not ask["escalated"] and "order number" in ask["content"].lower()
        found = _chat(ws_id(), "Order ORD-1001, my email is aarav@example.com. I want a refund", s)
    assert not found["escalated"] and OFFER_MARKER in found["content"]
    accepted = _chat(ws_id(), "yes please", s)                  # only now is a person involved
    assert accepted["escalated"] and len(_escalations(accepted["conversation_id"])) == 1


def test_9_no_thats_wrong_corrects_the_misunderstanding_using_the_previous_topic():
    s = uuid.uuid4().hex[:10]
    _chat(ws_id(), "What is your return policy?", s)
    assert IntentRouter.route_by_rules("No, that's wrong").intent == RouterIntent.CORRECTION
    r = _quiet("No, that's wrong", s)
    assert "return policy" in r["content"].lower() and "?" in r["content"]


# ══════════════════ the root cause: an open escalation must not silence the assistant ═════════
def test_unclaimed_escalation_does_not_lock_the_conversation():
    s = uuid.uuid4().hex[:10]
    first = _chat(ws_id(), "I want to talk to a human", s)
    assert first["escalated"]
    # the request is queued but no agent has picked it up: the assistant keeps helping
    hi = _quiet("Hi", s)
    assert "passed this on" not in hi["content"] and "teammate" not in hi["content"].lower()
    sorry = _quiet("I didn't say anything", s)
    assert sorry["content"] != hi["content"]
    assert any(w in sorry["content"].lower() for w in ("sorry", "mistake", "you're right"))
    # asking again does not open a second request or repeat the announcement
    again = _chat(ws_id(), "I want to talk to a human", s)
    assert again["escalated"] and "already" in again["content"].lower()
    assert len(_escalations(first["conversation_id"])) == 1


def test_once_an_agent_owns_the_conversation_replies_are_short_and_never_identical_back_to_back():
    s = uuid.uuid4().hex[:10]
    first = _chat(ws_id(), "I want to talk to a human", s)
    db = SessionLocal()
    try:
        for esc in db.query(HumanEscalation).filter(HumanEscalation.conversation_id == UUID(first["conversation_id"])).all():
            esc.status = EscalationStatus.IN_PROGRESS
        db.commit()
    finally:
        db.close()
    replies = [_chat(ws_id(), f"any update {i}?", s)["content"] for i in range(3)]
    assert all(r.strip() for r in replies) and len(set(replies)) == 3


# ══════════════════ escalation is never a fallback for uncertainty ═════════════════════════════
def test_ambiguous_or_short_messages_clarify_and_never_escalate():
    for text in ("return", "refund", "shipping"):
        d = IntentRouter.route_by_rules(text)
        assert d.route == Route.CLARIFY, text
        r = _quiet(text, uuid.uuid4().hex[:10])
        assert "?" in r["content"]


@pytest.mark.parametrize("text", ["Hi.", "Hello", "Thank you", "Okay", "Nice product", "I didn't say anything",
                                  "That's not what I asked", "Can you explain again?", "I am confused",
                                  "What do you mean?", "Good morning", "You are not understanding me"])
def test_messages_that_must_never_escalate(text):
    r = _quiet(text, uuid.uuid4().hex[:10])
    low = r["content"].lower()
    assert "passed this on" not in low and "teammate" not in low and "my team" not in low


def test_invalid_model_output_does_not_escalate():
    class Empty:
        model_name = "empty"

        def generate_response(self, **kw):
            return ""
    with patch("app.ai.orchestrator.get_llm_provider", return_value=Empty()), \
         patch("app.ai.orchestrator.ticket_auto.create_for_escalation", _Boom()):
        r = _chat(ws_id(), "What are your shipping charges?")
    assert not r["escalated"]


def test_missing_knowledge_is_an_honest_offer_then_escalates_only_on_yes():
    s = uuid.uuid4().hex[:10]
    with patch("app.ai.orchestrator.ticket_auto.create_for_escalation", _Boom()):
        offer = _chat(ws_id(), "What is the official policy on interstellar parcel drones?", s)
        assert not offer["escalated"] and OFFER_MARKER in offer["content"]
        declined = _chat(ws_id(), "no thanks", s)
    assert not declined["escalated"]
    offer2 = _chat(ws_id(), "What is the official policy on interstellar parcel drones?", s)
    yes = _chat(ws_id(), "yes", s)
    assert OFFER_MARKER in offer2["content"] and yes["escalated"]


def test_business_api_failure_has_its_own_message_and_no_escalation():
    from app.ai.tools.base import ToolResult
    boom = ToolResult(success=False, tool_name="order_tracking", error="db timeout")
    with patch("app.ai.planner.planner.tool_registry.execute_tool", return_value=boom), \
         patch("app.ai.orchestrator.ticket_auto.create_for_escalation", _Boom()):
        r = _chat(ws_id(), "Where is my order #ORD-1001? My email is aarav@example.com")
    assert not r["escalated"] and "trouble checking" in r["content"]


def test_outbound_check_blocks_claims_of_actions_that_never_happened():
    text, issues = enforce_outbound("Your refund is covered. I've passed this on to my teammate who is looking into it.", escalated=False)
    assert issues and "passed this on" not in text
    same, none = enforce_outbound("I've passed this on to my teammate.", escalated=True)
    assert not none and same.startswith("I've passed")


# ══════════════════ Telegram: /start, buttons, idempotency, failures ═════════════════════════════
def _upd(text, chat, uid=None, mid=None, name="Yash"):
    n = next(_ids)
    return {"update_id": uid or n, "message": {"message_id": mid or n, "chat": {"id": chat},
                                              "from": {"first_name": name, "id": chat}, "text": text}}


def _tap(data, chat, name="Yash"):
    return {"update_id": next(_ids), "callback_query": {"id": "cb", "data": data, "from": {"first_name": name},
                                                       "message": {"chat": {"id": chat}}}}


def _tg(payload):
    """Run one Telegram update through parse + handle with outbound sends captured. Returns (response|None, sent)."""
    sent: list[str] = []
    with patch.object(TelegramAdapter, "send_telegram_message",
                      side_effect=lambda chat_id, text, buttons=None: sent.append(text) or True), \
         patch.object(TelegramAdapter, "answer_callback"):
        incoming = TelegramAdapter.parse_webhook_payload(payload)
        if incoming is None:
            return None, sent
        db = SessionLocal()
        try:
            return TelegramAdapter().handle_incoming_message(db, UUID(ws_id()), incoming), sent
        finally:
            db.close()


def test_start_is_short_and_not_repeated_like_onboarding():
    chat = next(_ids)
    _, sent = _tg(_upd("/start", chat))
    assert len(sent) == 1 and len(sent[0]) < 90 and sent[0].startswith("Hey Yash!") and "support team" not in sent[0]
    assert "send the order number" not in sent[0]            # capabilities are explained on /help, not on every start
    _tg(_upd("Hi", chat))
    _, again = _tg(_upd("/start", chat))
    assert again[0].startswith("Hey again") and "Welcome" not in again[0]
    _, helped = _tg(_upd("/help", chat))
    assert "order" in helped[0].lower() and len(helped[0]) < 400


def test_buttons_start_their_own_workflow():
    from app.ai import orchestrator as orch
    # Talk to support -> explicit human escalation
    chat = next(_ids)
    resp, _ = _tg(_tap("q:human", chat))
    assert resp.escalated and len(_escalations(resp.conversation_id)) == 1
    # Return policy -> RAG
    calls = []
    real = orch.RAGRetriever.retrieve_with_plan

    def spy(self, *a, **k):
        calls.append(1)
        return real(self, *a, **k)
    with patch.object(orch.RAGRetriever, "retrieve_with_plan", spy):
        r, _ = _tg(_tap("q:returns", next(_ids)))
    assert calls and not r.escalated
    # Track my order -> order workflow (no retrieval, asks for the order number)
    with patch("app.ai.orchestrator.RAGRetriever", _Explode):
        t, sent = _tg(_tap("q:track", next(_ids)))
    assert not t.escalated and "order number" in sent[0].lower()


def test_ordinary_text_is_not_treated_as_a_button_press():
    r, _ = _tg(_upd("Track my order", next(_ids)))
    assert not r.escalated


def test_the_same_update_delivered_twice_gets_one_reply():
    chat, uid = next(_ids), next(_ids)
    payload = _upd("What are your shipping charges?", chat, uid=uid, mid=uid)
    first, sent1 = _tg(payload)
    second, sent2 = _tg(dict(payload))
    assert first is not None and second is None and len(sent1) == 1 and sent2 == []


def test_two_simultaneous_deliveries_are_processed_exactly_once():
    chat, uid = next(_ids), next(_ids)
    payload = _upd("Thank you", chat, uid=uid, mid=uid)
    results, sent = [], []
    barrier = threading.Barrier(2)

    def run():
        barrier.wait()
        with patch.object(TelegramAdapter, "send_telegram_message",
                          side_effect=lambda chat_id, text, buttons=None: sent.append(text) or True):
            incoming = TelegramAdapter.parse_webhook_payload(dict(payload))
            if incoming:
                db = SessionLocal()
                try:
                    results.append(TelegramAdapter().handle_incoming_message(db, UUID(ws_id()), incoming))
                finally:
                    db.close()
    threads = [threading.Thread(target=run) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 1 and len(sent) == 1


def test_the_same_message_in_a_new_update_is_also_ignored():
    chat, mid = next(_ids), next(_ids)
    _tg(_upd("Hi", chat, mid=mid))
    again, sent = _tg(_upd("Hi", chat, mid=mid))      # different update_id, same Telegram message_id (re-send / edit)
    assert again is None and sent == []


def test_internal_failure_gets_its_own_message_and_the_retry_is_processed_without_a_duplicate_message():
    chat, uid = next(_ids), next(_ids)
    payload = _upd("What are your shipping charges?", chat, uid=uid, mid=uid)
    with patch("app.channels.telegram_adapter.ConversationOrchestrator.process_turn", side_effect=RuntimeError("boom")):
        resp, sent = _tg(payload)
    assert resp.decision == "ERROR" and sent == [INTERNAL_ERROR] and not resp.escalated
    assert "teammate" not in sent[0].lower() and "passed" not in sent[0].lower()
    retry, sent2 = _tg(dict(payload))                  # Telegram retries the failed update
    assert retry is not None and retry.decision == "ANSWER" and len(sent2) == 1
    db = SessionLocal()
    try:
        from app.conversation.message_model import Message, MessageSenderType
        n = db.query(Message).filter(Message.conversation_id == retry.conversation_id,
                                     Message.sender_type == MessageSenderType.CUSTOMER,
                                     Message.content == "What are your shipping charges?").count()
    finally:
        db.close()
    assert n == 1


def test_deduper_and_chat_lock_primitives():
    d = UpdateDeduper(ttl_seconds=60, max_entries=3)
    assert d.claim("a") and not d.claim("a")
    d.release("a")
    assert d.claim("a")
    for k in "bcd":
        d.claim(k)
    assert d.claim("a")                                 # evicted by the size cap
    locks, order = ChatLocks(), []

    def work(n):
        with locks.guard("chat"):
            order.append(("in", n))
            order.append(("out", n))
    ts = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert all(order[i][0] == "in" and order[i + 1] == ("out", order[i][1]) for i in range(0, 8, 2))


def test_refund_meaning_continues_only_for_bare_details_not_for_a_new_question():
    s = uuid.uuid4().hex[:10]
    a, b = _no_rag_no_escalation()
    with a, b:
        _chat(ws_id(), "I want a refund", s)
        fresh = _chat(ws_id(), "Where is my order?", s)           # a new question: not a refund any more
    assert "refund" not in fresh["content"].lower()
    s2 = uuid.uuid4().hex[:10]
    with a, b:
        _chat(ws_id(), "I want a refund", s2)
        details = _chat(ws_id(), "ORD-1001", s2)                  # bare details: still the refund request
    assert "refund" in details["content"].lower() or "email" in details["content"].lower()
