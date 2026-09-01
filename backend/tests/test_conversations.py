import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_7_conversation_and_message_management():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        suffix_b = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # SETUP WORKSPACE A: Owner A, Admin A, Agent A, Customer A
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace A with Owner, Admin, Agent, and Customer ---")
        # 1. Register Owner A
        reg_owner_a = client.post(
            "/auth/register",
            json={
                "company_name": f"WS Alpha {suffix_a}",
                "company_slug": f"ws-alpha-{suffix_a}",
                "full_name": "Owner Alpha",
                "email": f"owner_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_token = reg_owner_a.json()["token"]["access_token"]
        owner_a_refresh_token = reg_owner_a.json()["token"]["refresh_token"]
        owner_a_id = reg_owner_a.json()["user"]["id"]

        # 2. Owner A creates Admin A
        create_admin_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha",
                "email": f"admin_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert create_admin_a.status_code == 201
        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]
        admin_a_id = create_admin_a.json()["id"]

        # 3. Owner A creates Agent A
        create_agent_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha",
                "email": f"agent_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert create_agent_a.status_code == 201
        login_agent_a = client.post(
            "/auth/login",
            data={"username": f"agent_a_{suffix_a}@example.com", "password": password},
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]
        agent_a_id = create_agent_a.json()["id"]

        # 4. Create Customer A in Workspace A
        create_cust_a = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Customer Alpha",
                "email": f"cust_a_{suffix_a}@example.com",
                "phone": "+1111111111",
                "company_name": "Acme Alpha",
            },
        )
        assert create_cust_a.status_code == 201
        customer_a_id = create_cust_a.json()["id"]

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B, Customer B
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace B with Owner and Customer ---")
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"WS Beta {suffix_b}",
                "company_slug": f"ws-beta-{suffix_b}",
                "full_name": "Owner Beta",
                "email": f"owner_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_token = reg_owner_b.json()["token"]["access_token"]

        create_cust_b = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "full_name": "Customer Beta",
                "email": f"cust_b_{suffix_b}@example.com",
                "phone": "+2222222222",
                "company_name": "Beta Corp",
            },
        )
        assert create_cust_b.status_code == 201
        customer_b_id = create_cust_b.json()["id"]

        # =============================================================
        # 1. OWNER creates conversation
        # =============================================================
        print("\n--- Test 1: OWNER creates conversation ---")
        conv1_res = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "customer_id": customer_a_id,
                "subject": "Billing issue with invoice #101",
            },
        )
        assert conv1_res.status_code == 201, f"Failed: {conv1_res.text}"
        conv1_data = conv1_res.json()
        conv1_id = conv1_data["id"]
        assert conv1_data["subject"] == "Billing issue with invoice #101"
        assert conv1_data["status"] == "open"
        assert conv1_data["customer_id"] == customer_a_id

        # =============================================================
        # 2. ADMIN creates conversation
        # =============================================================
        print("\n--- Test 2: ADMIN creates conversation ---")
        conv2_res = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "customer_id": customer_a_id,
                "subject": "Technical question about API limits",
            },
        )
        assert conv2_res.status_code == 201
        conv2_id = conv2_res.json()["id"]

        # =============================================================
        # 3. AGENT creates conversation
        # =============================================================
        print("\n--- Test 3: AGENT creates conversation ---")
        conv3_res = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "customer_id": customer_a_id,
                "subject": "Password reset inquiry",
            },
        )
        assert conv3_res.status_code == 201
        conv3_id = conv3_res.json()["id"]

        # =============================================================
        # 4. Unauthenticated creation rejected (401)
        # =============================================================
        print("\n--- Test 4: Unauthenticated creation rejected (401) ---")
        unauth_conv = client.post(
            "/conversations",
            json={
                "customer_id": customer_a_id,
                "subject": "Unauthorized ticket",
            },
        )
        assert unauth_conv.status_code == 401

        # =============================================================
        # 5. List conversations
        # =============================================================
        print("\n--- Test 5: List conversations ---")
        list_res = client.get(
            "/conversations",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert list_res.status_code == 200
        conv_list = list_res.json()
        assert len(conv_list) >= 3
        conv_ids = [c["id"] for c in conv_list]
        assert conv1_id in conv_ids
        assert conv2_id in conv_ids
        assert conv3_id in conv_ids

        # =============================================================
        # 6. Get conversation by ID
        # =============================================================
        print("\n--- Test 6: Get conversation by ID ---")
        get_conv = client.get(
            f"/conversations/{conv1_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert get_conv.status_code == 200
        assert get_conv.json()["id"] == conv1_id
        assert get_conv.json()["subject"] == "Billing issue with invoice #101"

        # =============================================================
        # 7. Update conversation subject & 8. Update status
        # =============================================================
        print("\n--- Tests 7 & 8: Update conversation subject and status ---")
        patch_res = client.patch(
            f"/conversations/{conv1_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "subject": "Resolved: Billing issue with invoice #101",
                "status": "resolved",
            },
        )
        assert patch_res.status_code == 200
        updated_conv = patch_res.json()
        assert updated_conv["subject"] == "Resolved: Billing issue with invoice #101"
        assert updated_conv["status"] == "resolved"

        # =============================================================
        # 9. Create agent message & 10. sender_user_id automatically assigned
        # =============================================================
        print("\n--- Tests 9 & 10: Create AGENT message & sender_user_id verification ---")
        msg1_res = client.post(
            f"/conversations/{conv1_id}/messages",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "content": "Hello! I am looking into your invoice right now.",
                "sender_type": "agent",
            },
        )
        assert msg1_res.status_code == 201, f"Failed: {msg1_res.text}"
        msg1_data = msg1_res.json()
        msg1_id = msg1_data["id"]
        assert msg1_data["conversation_id"] == conv1_id
        assert msg1_data["sender_type"] == "agent"
        assert msg1_data["sender_user_id"] == agent_a_id
        assert msg1_data["content"] == "Hello! I am looking into your invoice right now."

        # Create SYSTEM message (sender_user_id is None)
        print("\n--- Test: Create SYSTEM message ---")
        msg2_res = client.post(
            f"/conversations/{conv1_id}/messages",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "content": "Status changed to RESOLVED by system workflow.",
                "sender_type": "system",
            },
        )
        assert msg2_res.status_code == 201
        msg2_data = msg2_res.json()
        assert msg2_data["sender_type"] == "system"
        assert msg2_data["sender_user_id"] is None

        # =============================================================
        # 11. List messages chronologically
        # =============================================================
        print("\n--- Test 11: List messages chronologically ---")
        list_msgs = client.get(
            f"/conversations/{conv1_id}/messages",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert list_msgs.status_code == 200
        msgs = list_msgs.json()
        assert len(msgs) >= 2
        assert msgs[0]["id"] == msg1_id
        assert msgs[1]["id"] == msg2_data["id"]
        assert msgs[0]["created_at"] <= msgs[1]["created_at"]

        # -------------------------------------------------------------
        # Setup Conversation in Workspace B
        # -------------------------------------------------------------
        conv_b_res = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "customer_id": customer_b_id,
                "subject": "Workspace B confidential ticket",
            },
        )
        assert conv_b_res.status_code == 201
        conv_b_id = conv_b_res.json()["id"]

        # Add message in Workspace B
        client.post(
            f"/conversations/{conv_b_id}/messages",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "content": "Confidential message in Workspace B",
                "sender_type": "agent",
            },
        )

        # =============================================================
        # 12. Cross-workspace conversation access returns 404
        # =============================================================
        print("\n--- Test 12: Cross-workspace conversation access returns 404 ---")
        cross_get_conv = client.get(
            f"/conversations/{conv_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_get_conv.status_code == 404

        # =============================================================
        # 13. Cross-workspace conversation update returns 404
        # =============================================================
        print("\n--- Test 13: Cross-workspace conversation update returns 404 ---")
        cross_patch_conv = client.patch(
            f"/conversations/{conv_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"subject": "Hacked Subject"},
        )
        assert cross_patch_conv.status_code == 404

        # =============================================================
        # 14. Cross-workspace message access returns 404
        # =============================================================
        print("\n--- Test 14: Cross-workspace message access returns 404 ---")
        cross_get_msgs = client.get(
            f"/conversations/{conv_b_id}/messages",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_get_msgs.status_code == 404

        cross_post_msg = client.post(
            f"/conversations/{conv_b_id}/messages",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"content": "Hacked Message", "sender_type": "agent"},
        )
        assert cross_post_msg.status_code == 404

        # =============================================================
        # 15. Invalid customer ID returns 404
        # =============================================================
        print("\n--- Test 15: Invalid customer ID returns 404 ---")
        random_cust_id = str(uuid.uuid4())
        invalid_cust_conv = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "customer_id": random_cust_id,
                "subject": "Ticket with non-existent customer",
            },
        )
        assert invalid_cust_conv.status_code == 404

        # =============================================================
        # 16. Invalid conversation ID returns 404
        # =============================================================
        print("\n--- Test 16: Non-existent conversation ID returns 404 ---")
        random_conv_id = str(uuid.uuid4())
        non_existent_conv = client.get(
            f"/conversations/{random_conv_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert non_existent_conv.status_code == 404

        # =============================================================
        # 17. Invalid token returns 401
        # =============================================================
        print("\n--- Test 17: Invalid token returns 401 ---")
        bad_token = client.get(
            "/conversations",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert bad_token.status_code == 401

        # =============================================================
        # 18. Refresh token used as access token returns 401
        # =============================================================
        print("\n--- Test 18: Refresh token used as access token returns 401 ---")
        refresh_as_access = client.get(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert refresh_as_access.status_code == 401

        # =============================================================
        # 19. Customer from another workspace cannot be used to create conversation
        # =============================================================
        print("\n--- Test 19: Cross-workspace customer cannot be used in conversation (404) ---")
        cross_cust_create = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "customer_id": customer_b_id,  # customer belongs to Workspace B
                "subject": "Ticket targeting Workspace B customer",
            },
        )
        assert cross_cust_create.status_code == 404

        print("\n ALL CONVERSATION AND MESSAGE MANAGEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_7_conversation_and_message_management()
