"""Telegram channel: commands, typing, non-text, dedupe, splitting, webhook secret, grounded answers."""
import itertools
import uuid
from unittest.mock import patch

import httpx

from app.core.config import settings
from app.database.database import SessionLocal
from app.conversation.message_model import Message
from tests.test_rag_pipeline import POLICY_TEXT, _upload, _wait, _workspace, client  # imports app.main first
from app.channels.telegram_adapter import TELEGRAM_MAX_LEN, TelegramAdapter

_update_ids = itertools.count(int(uuid.uuid4().int % 10_000_000) * 100)


def update(text=None, chat_id=555000111, user="Maya", **extra):
    msg = {"message_id": next(_update_ids), "chat": {"id": chat_id},
           "from": {"first_name": user, "username": "maya_tg", "is_bot": False}}
    if text is not None:
        msg["text"] = text
    msg.update(extra)
    return {"update_id": next(_update_ids), "message": msg}


def handle(ws_id, payload):
    """Run one Telegram update through the adapter, capturing what would be sent to the user."""
    sent: list[str] = []
    with patch.object(TelegramAdapter, "send_telegram_message", side_effect=lambda chat_id, text, **kw: sent.append(text) or True), \
         patch.object(TelegramAdapter, "send_chat_action"):
        incoming = TelegramAdapter.parse_webhook_payload(payload)
        response = None
        if incoming:
            db = SessionLocal()
            try:
                response = TelegramAdapter().handle_incoming_message(db=db, workspace_id=uuid.UUID(ws_id), incoming=incoming)
            finally:
                db.close()
    return incoming, response, sent


def test_start_and_help_are_answered_without_the_ai():
    ws, H, src = _workspace()
    for cmd, needle in (("/start", "How can I help you today?"), ("/help", "I can help with"), ("/start@CortexCX_bot", "How can I help")):
        incoming, resp, sent = handle(ws, update(cmd, chat_id=int(uuid.uuid4().int % 10**9)))
        assert resp.decision == "ANSWER" and not resp.escalated
        assert len(sent) == 1 and needle in sent[0]
    # /start mentions the store and does not create an escalation or an AI message
    _, _, sent = handle(ws, update("/start", chat_id=777000222))
    assert "RAG" in sent[0]  # workspace name is "RAG <tag>"
    db = SessionLocal()
    try:
        from app.escalation.model import HumanEscalation

        assert db.query(HumanEscalation).filter(HumanEscalation.workspace_id == ws).count() == 0
    finally:
        db.close()


def test_question_is_answered_from_documents_and_conversation_is_reused():
    ws, H, src = _workspace()
    _wait(H, _upload(H, src, "help.txt", POLICY_TEXT.encode()).json()["id"])
    chat = int(uuid.uuid4().int % 10**9)

    _, r1, sent1 = handle(ws, update("How many days do I have to return unworn items?", chat_id=chat))
    assert r1.decision == "ANSWER" and "45 days" in sent1[0]
    assert r1.sources and r1.sources[0]["section"] == "Returns"

    _, r2, sent2 = handle(ws, update("And what does standard shipping cost?", chat_id=chat))
    assert r2.conversation_id == r1.conversation_id          # same Telegram chat -> same conversation
    assert "6.95" in sent2[0]

    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.conversation_id == r1.conversation_id).count()
        assert msgs == 4                                       # 2 customer + 2 assistant
    finally:
        db.close()


def test_unanswerable_question_hands_off_honestly():
    ws, H, src = _workspace()
    _wait(H, _upload(H, src, "help.txt", POLICY_TEXT.encode()).json()["id"])
    _, resp, sent = handle(ws, update("What is the capital of France?"))
    assert not resp.escalated and "bring in the team" in sent[0]


def test_non_text_messages_get_a_reply_instead_of_silence():
    ws, H, src = _workspace()
    incoming, resp, sent = handle(ws, update(None, photo=[{"file_id": "x"}]))
    assert incoming is None and resp is None
    assert len(sent) == 1 and "only read text" in sent[0]


def test_duplicate_updates_are_processed_once():
    ws, H, src = _workspace()
    payload = update("/start")
    _, first, sent1 = handle(ws, payload)
    _, second, sent2 = handle(ws, payload)  # Telegram retries the same update
    assert first is not None and second is None and sent2 == []


def test_long_replies_are_split_for_telegram():
    calls = []

    class FakeClient:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, **k):
            calls.append(json["text"])
            return httpx.Response(200, json={"ok": True})

    old = settings.TELEGRAM_BOT_TOKEN
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    try:
        with patch("app.channels.telegram_adapter.httpx.Client", FakeClient):
            assert TelegramAdapter.send_telegram_message(1, "x" * (TELEGRAM_MAX_LEN * 2 + 50)) is True
    finally:
        settings.TELEGRAM_BOT_TOKEN = old
    assert [len(c) for c in calls] == [TELEGRAM_MAX_LEN, TELEGRAM_MAX_LEN, 50]


def test_send_failure_is_reported_not_raised():
    class FakeClient:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return httpx.Response(400, text="chat not found")

    old = settings.TELEGRAM_BOT_TOKEN
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    try:
        with patch("app.channels.telegram_adapter.httpx.Client", FakeClient):
            assert TelegramAdapter.send_telegram_message(1, "hi") is False
    finally:
        settings.TELEGRAM_BOT_TOKEN = old


def test_webhook_requires_the_secret_when_configured():
    ws, H, src = _workspace()
    old = settings.TELEGRAM_WEBHOOK_SECRET
    settings.TELEGRAM_WEBHOOK_SECRET = "s3cret-value"
    try:
        url = f"/channels/telegram/webhook?workspace_id={ws}"
        assert client.post(url, json=update("/start")).status_code == 403
        assert client.post(url, json=update("/start"), headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code == 403
        ok = client.post(url, json=update("/start"), headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret-value"})
        assert ok.status_code == 200 and ok.json()["status"] == "ok"
    finally:
        settings.TELEGRAM_WEBHOOK_SECRET = old
