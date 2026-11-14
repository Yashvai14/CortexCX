import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PASSWORD = "SecurePassword123!"


def _register(suffix: str, label: str):
    r = client.post(
        "/auth/register",
        json={
            "company_name": f"Tix {label} {suffix}",
            "company_slug": f"tix-{label}-{suffix}",
            "full_name": f"Owner {label}",
            "email": f"tix_{label}_{suffix}@example.com",
            "password": PASSWORD,
        },
    )
    assert r.status_code in (200, 201), r.text
    login = client.post(
        "/auth/login",
        data={"username": f"tix_{label}_{suffix}@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, r.json()["user"]["id"]


def test_ticket_lifecycle_and_isolation():
    suffix = uuid.uuid4().hex[:8]
    a, a_user = _register(suffix, "a")
    b, _ = _register(suffix, "b")

    # create — numbering starts at 1001 per workspace
    r = client.post("/tickets", headers=a, json={"subject": "Refund not received", "priority": "urgent"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["reference"] == "TCK-1001"
    assert t["status"] == "open"
    assert t["due_at"] is not None
    assert t["comments"][0]["is_event"] is True

    t2 = client.post("/tickets", headers=a, json={"subject": "Wrong size shipped"}).json()
    assert t2["reference"] == "TCK-1002"

    # numbering is independent per workspace
    tb = client.post("/tickets", headers=b, json={"subject": "Other workspace"}).json()
    assert tb["reference"] == "TCK-1001"

    # tenant isolation
    assert client.get(f"/tickets/{t['id']}", headers=b).status_code == 404
    assert client.patch(f"/tickets/{t['id']}", headers=b, json={"status": "closed"}).status_code == 404

    # assign -> open auto-moves to in_progress
    r = client.patch(f"/tickets/{t['id']}", headers=a, json={"assignee_id": a_user})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert r.json()["assignee"]["id"] == a_user

    # cannot assign to a user outside the workspace
    assert (
        client.patch(f"/tickets/{t['id']}", headers=a, json={"assignee_id": str(uuid.uuid4())}).status_code
        == 400
    )

    # internal note does not set first response; public reply does
    client.post(f"/tickets/{t['id']}/comments", headers=a, json={"content": "checking", "is_internal": True})
    assert client.get(f"/tickets/{t['id']}", headers=a).json()["first_response_at"] is None
    client.post(f"/tickets/{t['id']}/comments", headers=a, json={"content": "Refund issued"})
    assert client.get(f"/tickets/{t['id']}", headers=a).json()["first_response_at"] is not None

    # resolve stamps resolved_at; reopening clears it
    r = client.patch(f"/tickets/{t['id']}", headers=a, json={"status": "resolved"}).json()
    assert r["resolved_at"] is not None
    r = client.patch(f"/tickets/{t['id']}", headers=a, json={"status": "open"}).json()
    assert r["resolved_at"] is None

    # filters, search, stats
    assert len(client.get("/tickets", headers=a).json()) == 2
    assert len(client.get("/tickets?priority=urgent", headers=a).json()) == 1
    assert len(client.get("/tickets?q=TCK-1002", headers=a).json()) == 1
    assert len(client.get("/tickets?q=refund", headers=a).json()) == 1
    assert len(client.get("/tickets?unassigned=true", headers=a).json()) == 1
    stats = client.get("/tickets/stats", headers=a).json()
    assert stats["total"] == 2
    assert stats["unassigned"] == 1

    # delete (owner is admin-level)
    assert client.delete(f"/tickets/{t2['id']}", headers=a).status_code == 204
    assert client.get(f"/tickets/{t2['id']}", headers=a).status_code == 404

    # auth required
    assert client.get("/tickets").status_code in (401, 403)


def test_ticket_linked_to_conversation():
    suffix = uuid.uuid4().hex[:8]
    a, _ = _register(suffix, "c")
    b, _ = _register(suffix, "d")

    cust = client.post("/customers", headers=a, json={"full_name": "Link Cust", "email": f"l_{suffix}@example.com"}).json()
    conv = client.post("/conversations", headers=a, json={"customer_id": cust["id"], "subject": "Help"}).json()
    assert "id" in conv, conv

    t = client.post(
        "/tickets",
        headers=a,
        json={"subject": "From conversation", "conversation_id": conv["id"], "customer_id": cust["id"]},
    )
    assert t.status_code == 201, t.text
    assert t.json()["conversation_id"] == conv["id"]
    client.post("/tickets", headers=a, json={"subject": "Unrelated ticket"})

    linked = client.get(f"/tickets?conversation_id={conv['id']}", headers=a).json()
    assert [x["subject"] for x in linked] == ["From conversation"]

    # another workspace cannot link to this conversation or customer
    assert client.post("/tickets", headers=b, json={"subject": "Steal link", "conversation_id": conv["id"]}).status_code == 400
    assert client.post("/tickets", headers=b, json={"subject": "Steal cust", "customer_id": cust["id"]}).status_code == 400
