"""Escalation -> ticket automation, including customer confirmation before resolving."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PW = "SecurePassword123!"


def _setup():
    s = uuid.uuid4().hex[:8]
    r = client.post("/auth/register", json={
        "company_name": "Auto Store", "company_slug": f"auto-{s}", "full_name": "Auto Owner",
        "email": f"auto_{s}@example.com", "password": PW,
    })
    assert r.status_code == 201, r.text
    tok = client.post("/auth/login", data={"username": f"auto_{s}@example.com", "password": PW}).json()["access_token"]
    return r.json()["workspace"]["id"], {"Authorization": f"Bearer {tok}"}


def _chat(ws, session, text):
    r = client.post("/channels/webchat/message", json={
        "workspace_id": ws, "session_id": session, "content": text, "customer_name": "Riya"})
    assert r.status_code == 200, r.text
    return r.json()


def _ticket(h):
    items = client.get("/tickets", headers=h).json()
    items = items["items"] if isinstance(items, dict) else items
    assert len(items) == 1, items
    return client.get(f"/tickets/{items[0]['id']}", headers=h).json()


def _flow(confirmation: str):
    ws, h = _setup()
    sess = uuid.uuid4().hex[:10]
    _chat(ws, sess, "I want to talk to a human")

    t = _ticket(h)
    assert t["status"] == "open" and t["category"] == "Escalation"

    esc = client.get("/escalations", headers=h).json()
    esc = esc["items"] if isinstance(esc, dict) else esc
    eid = esc[0]["id"]

    assert client.post(f"/escalations/{eid}/claim", headers=h).status_code == 200
    t = _ticket(h)
    assert t["status"] == "in_progress" and t["assignee"] is not None

    r = client.post(f"/escalations/{eid}/respond", headers=h, json={"content": "Refund issued.", "resolve": True})
    assert r.json()["awaiting_customer_confirmation"] is True
    assert _ticket(h)["status"] == "waiting"

    hist = client.get(f"/channels/webchat/history/{sess}", params={"workspace_id": ws}).json()
    assert hist["ai_state"] == "awaiting_confirmation"

    _chat(ws, sess, confirmation)
    return _ticket(h) if confirmation.lower().startswith("no") else client.get("/tickets", headers=h).json()


def test_customer_confirms_resolution_closes_ticket():
    out = _flow("Yes, it's resolved")
    items = out["items"] if isinstance(out, dict) else out
    assert items[0]["status"] == "resolved"


def test_customer_rejects_resolution_reopens_ticket():
    t = _flow("No, I still need help")
    assert t["status"] == "in_progress"


def test_telegram_agent_reply_confirmation_buttons_and_personalisation():
    from unittest.mock import patch

    from app.channels.telegram_adapter import TelegramAdapter
    from app.core.config import settings

    ws, h = _setup()
    sent: list[tuple] = []
    hdr = {"x-telegram-bot-api-secret-token": settings.TELEGRAM_WEBHOOK_SECRET} if settings.TELEGRAM_WEBHOOK_SECRET else {}
    chat_id = int(uuid.uuid4().int % 10**9)
    n = [0]

    def hook(update_body):
        n[0] += 1
        return client.post("/channels/telegram/webhook", params={"workspace_id": ws}, json=update_body, headers=hdr)

    def msg(text):
        return hook({"update_id": uuid.uuid4().int % 10**9, "message": {
            "message_id": n[0] + 1, "chat": {"id": chat_id}, "text": text,
            "from": {"first_name": "Riya", "last_name": "Kapoor", "username": "riya"}}})

    def tap(data):
        return hook({"update_id": uuid.uuid4().int % 10**9, "callback_query": {
            "id": "cb1", "data": data, "from": {"first_name": "Riya"}, "message": {"chat": {"id": chat_id}}}})

    with patch.object(TelegramAdapter, "send_telegram_message",
                      side_effect=lambda chat_id, text, buttons=None: sent.append((text, buttons)) or True), \
         patch.object(TelegramAdapter, "answer_callback"):
        msg("/start")
        assert sent[-1][0].startswith("Hey Riya!") and sent[-1][1], sent[-1]

        tap("q:human")  # inline "Talk to a human" button
        t = _ticket(h)
        assert t["status"] == "open"

        esc = client.get("/escalations", headers=h).json()
        eid = (esc["items"] if isinstance(esc, dict) else esc)[0]["id"]
        client.post(f"/escalations/{eid}/claim", headers=h)
        assert "will help you personally" in sent[-1][0] and "Riya" in sent[-1][0]

        client.post(f"/escalations/{eid}/respond", headers=h, json={"content": "Refund issued.", "resolve": True})
        texts = [s[0] for s in sent]
        assert any("from support:\nRefund issued." in x for x in texts)
        prompt, buttons = sent[-1]
        assert prompt.startswith("Riya, ") and buttons and len(buttons[0]) == 2

        tap("confirm:yes")  # customer taps the button
    assert _ticket_status(h) == "resolved"


def _ticket_status(h):
    items = client.get("/tickets", headers=h).json()
    return (items["items"] if isinstance(items, dict) else items)[0]["status"]
