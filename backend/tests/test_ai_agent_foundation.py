import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.model import User
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_9_ai_agent_foundation():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        suffix_b = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # SETUP WORKSPACE A: Owner A, Agent A, Customer A, Conversation A
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace A with Owner, Agent, Customer, and Conversation ---")
        # 1. Register Owner A
        reg_owner_a = client.post(
            "/auth/register",
            json={
                "company_name": f"AI Corp Alpha {suffix_a}",
                "company_slug": f"ai-alpha-{suffix_a}",
                "full_name": "Owner Alpha AI",
                "email": f"owner_ai_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        owner_a_id = owner_a_data["user"]["id"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # 2. Add Agent A
        add_agent_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha AI",
                "email": f"agent_ai_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={
                "username": f"agent_ai_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]

        # 3. Create Customer A
        create_cust_a = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Customer AI Alpha",
                "email": f"cust_ai_a_{suffix_a}@example.com",
                "phone": "+1999999999",
                "company_name": "AI Alpha Client",
            },
        )
        assert create_cust_a.status_code == 201
        customer_a_id = create_cust_a.json()["id"]

        # 4. Create Conversation A
        create_conv_a = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "customer_id": customer_a_id,
                "subject": "Help with AI API integration",
            },
        )
        assert create_conv_a.status_code == 201
        conv_a_id = create_conv_a.json()["id"]

        # Add initial user message
        client.post(
            f"/conversations/{conv_a_id}/messages",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "content": "Customer asked: How do I authenticate with the API?",
                "sender_type": "agent",
            },
        )

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B, Customer B, Conversation B
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace B with Owner, Customer, and Conversation ---")
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"AI Corp Beta {suffix_b}",
                "company_slug": f"ai-beta-{suffix_b}",
                "full_name": "Owner Beta AI",
                "email": f"owner_ai_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]

        create_cust_b = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "full_name": "Customer AI Beta",
                "email": f"cust_ai_b_{suffix_b}@example.com",
                "phone": "+2888888888",
                "company_name": "AI Beta Client",
            },
        )
        assert create_cust_b.status_code == 201
        customer_b_id = create_cust_b.json()["id"]

        create_conv_b = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "customer_id": customer_b_id,
                "subject": "Workspace B confidential ticket",
            },
        )
        assert create_conv_b.status_code == 201
        conv_b_id = create_conv_b.json()["id"]

        # =============================================================
        # 1. Authenticated user can process conversation
        # 2. AI message is persisted
        # 3. AI message has sender_type="ai", sender_user_id=None
        # 5. ai_state becomes "responded"
        # =============================================================
        print("\n--- Tests 1, 2, 3, 5: Process conversation with AI ---")
        process_res = client.post(
            f"/ai/conversations/{conv_a_id}/process",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={},
        )
        assert process_res.status_code == 200, f"Failed: {process_res.text}"
        ai_resp_data = process_res.json()
        assert ai_resp_data["conversation_id"] == conv_a_id
        assert ai_resp_data["ai_state"] == "responded"
        ai_msg = ai_resp_data["message"]
        assert ai_msg["sender_type"] == "ai"
        assert ai_msg["sender_user_id"] is None
        assert "Help with AI API integration" in ai_msg["content"]

        # =============================================================
        # 4. AI response appears in conversation messages list
        # =============================================================
        print("\n--- Test 4: AI response appears in conversation messages ---")
        messages_res = client.get(
            f"/conversations/{conv_a_id}/messages",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert messages_res.status_code == 200
        msgs = messages_res.json()
        assert len(msgs) >= 2
        ai_msgs_in_list = [m for m in msgs if m["sender_type"] == "ai"]
        assert len(ai_msgs_in_list) == 1
        assert ai_msgs_in_list[0]["sender_user_id"] is None

        # =============================================================
        # 6. AI status endpoint works
        # =============================================================
        print("\n--- Test 6: AI status endpoint returns accurate data ---")
        status_res = client.get(
            f"/ai/conversations/{conv_a_id}/status",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert status_res.status_code == 200
        stat = status_res.json()
        assert stat["conversation_id"] == conv_a_id
        assert stat["ai_enabled"] is True
        assert stat["ai_state"] == "responded"
        assert stat["total_ai_messages"] == 1
        assert stat["last_processed_at"] is not None

        # =============================================================
        # 7. AI toggle works & 8. Disabled AI blocks processing
        # =============================================================
        print("\n--- Tests 7 & 8: Toggle AI handling and block when disabled ---")
        # Toggle off
        toggle_off = client.patch(
            f"/ai/conversations/{conv_a_id}/toggle",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"ai_enabled": False},
        )
        assert toggle_off.status_code == 200
        assert toggle_off.json()["ai_enabled"] is False
        assert toggle_off.json()["ai_state"] == "disabled"

        # Attempt to process when disabled
        blocked_process = client.post(
            f"/ai/conversations/{conv_a_id}/process",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={},
        )
        assert blocked_process.status_code == 400
        assert "disabled" in blocked_process.text.lower()

        # Toggle back on
        toggle_on = client.patch(
            f"/ai/conversations/{conv_a_id}/toggle",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"ai_enabled": True},
        )
        assert toggle_on.status_code == 200
        assert toggle_on.json()["ai_enabled"] is True

        # Process with prompt override
        override_process = client.post(
            f"/ai/conversations/{conv_a_id}/process",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"prompt_override": "Custom escalation note for human agent."},
        )
        assert override_process.status_code == 200
        assert "Custom escalation note" in override_process.json()["message"]["content"]

        # Verify status counts updated to 2
        status_updated = client.get(
            f"/ai/conversations/{conv_a_id}/status",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert status_updated.status_code == 200
        assert status_updated.json()["total_ai_messages"] == 2

        # =============================================================
        # 9. Unauthenticated request returns 401
        # =============================================================
        print("\n--- Test 9: Unauthenticated request returns 401 ---")
        unauth_process = client.post(f"/ai/conversations/{conv_a_id}/process")
        assert unauth_process.status_code == 401

        # =============================================================
        # 10. Inactive user is rejected
        # =============================================================
        print("\n--- Test 10: Inactive user is rejected (400/401/403) ---")
        # Deactivate Agent A
        client.patch(
            f"/workspaces/users/{agent_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": False},
        )

        inactive_process = client.post(
            f"/ai/conversations/{conv_a_id}/process",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={},
        )
        assert inactive_process.status_code in [400, 401, 403]

        # Re-activate Agent A
        client.patch(
            f"/workspaces/users/{agent_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": True},
        )

        # =============================================================
        # 11, 12, 13. Cross-workspace AI processing, status, toggle return 404
        # =============================================================
        print("\n--- Tests 11, 12, 13: Cross-workspace access returns 404 ---")
        cross_process = client.post(
            f"/ai/conversations/{conv_b_id}/process",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={},
        )
        assert cross_process.status_code == 404

        cross_status = client.get(
            f"/ai/conversations/{conv_b_id}/status",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_status.status_code == 404

        cross_toggle = client.patch(
            f"/ai/conversations/{conv_b_id}/toggle",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"ai_enabled": False},
        )
        assert cross_toggle.status_code == 404

        # =============================================================
        # 14. Invalid conversation ID returns 404
        # =============================================================
        print("\n--- Test 14: Non-existent conversation ID returns 404 ---")
        random_conv_id = str(uuid.uuid4())
        non_existent = client.post(
            f"/ai/conversations/{random_conv_id}/process",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={},
        )
        assert non_existent.status_code == 404

        # =============================================================
        # 15. Refresh token cannot be used as an access token
        # =============================================================
        print("\n--- Test 15: Refresh token as access token returns 401 ---")
        refresh_as_access = client.post(
            f"/ai/conversations/{conv_a_id}/process",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
            json={},
        )
        assert refresh_as_access.status_code == 401

        print("\n ALL MILESTONE 9 AI AGENT FOUNDATION TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_9_ai_agent_foundation()
