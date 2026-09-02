import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_13_rag_generation():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        suffix_b = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # SETUP WORKSPACE A: Owner A, Admin A, Agent A
        # -------------------------------------------------------------
        reg_owner_a = client.post(
            "/auth/register",
            json={
                "company_name": f"RAG Corp Alpha {suffix_a}",
                "company_slug": f"rag-alpha-{suffix_a}",
                "full_name": "Owner Alpha RAG",
                "email": f"owner_rag_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # Admin A
        add_admin_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha RAG",
                "email": f"admin_rag_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert add_admin_a.status_code == 201
        admin_a_id = add_admin_a.json()["id"]

        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_rag_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # Agent A
        add_agent_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha RAG",
                "email": f"agent_rag_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={"username": f"agent_rag_a_{suffix_a}@example.com", "password": password},
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B
        # -------------------------------------------------------------
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"RAG Corp Beta {suffix_b}",
                "company_slug": f"rag-beta-{suffix_b}",
                "full_name": "Owner Beta RAG",
                "email": f"owner_rag_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # -------------------------------------------------------------
        # CREATE CUSTOMERS & CONVERSATIONS
        # -------------------------------------------------------------
        # Customer A
        res_cust_a = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"full_name": "Customer Alice", "email": f"alice_{suffix_a}@example.com"},
        )
        assert res_cust_a.status_code == 201
        cust_a_id = res_cust_a.json()["id"]

        # Conversation A
        res_conv_a = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"customer_id": cust_a_id, "subject": "Billing inquiry about subscription refunds"},
        )
        assert res_conv_a.status_code == 201
        conv_a_id = res_conv_a.json()["id"]

        # Customer message in DB for Conversation A
        msg_a = Message(
            conversation_id=uuid.UUID(conv_a_id),
            sender_type=MessageSenderType.CUSTOMER,
            sender_user_id=None,
            content="How do I request a refund for my subscription?",
        )
        db.add(msg_a)
        db.commit()

        # Customer B & Conversation B (in Workspace B)
        res_cust_b = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={"full_name": "Customer Bob", "email": f"bob_{suffix_b}@example.com"},
        )
        assert res_cust_b.status_code == 201
        cust_b_id = res_cust_b.json()["id"]

        res_conv_b = client.post(
            "/conversations",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={"customer_id": cust_b_id, "subject": "Confidential internal inquiry"},
        )
        assert res_conv_b.status_code == 201
        conv_b_id = res_conv_b.json()["id"]

        # -------------------------------------------------------------
        # CREATE & EMBED KNOWLEDGE IN WORKSPACE A
        # -------------------------------------------------------------
        res_src_a = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"name": "Refund Policy Doc", "source_type": "txt"},
        )
        assert res_src_a.status_code == 201
        src_a_id = res_src_a.json()["id"]

        res_doc_a = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "knowledge_source_id": src_a_id,
                "title": "Refund and Cancellation Policy",
                "content": "Customers can request a refund within 30 days of subscription purchase by contacting support.",
            },
        )
        assert res_doc_a.status_code == 201
        doc_a_id = res_doc_a.json()["id"]

        # Embed document chunks in Workspace A
        client.post(
            f"/knowledge/documents/{doc_a_id}/embed",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )

        # -------------------------------------------------------------
        # CREATE & EMBED CONFIDENTIAL KNOWLEDGE IN WORKSPACE B
        # -------------------------------------------------------------
        res_src_b = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={"name": "Confidential Workspace B Info", "source_type": "txt"},
        )
        assert res_src_b.status_code == 201
        src_b_id = res_src_b.json()["id"]

        res_doc_b = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "knowledge_source_id": src_b_id,
                "title": "Confidential Security Codes",
                "content": "Secret security code: ALPHA-BETA-999-SECRET-TOKEN",
            },
        )
        assert res_doc_b.status_code == 201
        doc_b_id = res_doc_b.json()["id"]

        client.post(
            f"/knowledge/documents/{doc_b_id}/embed",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )

        # =============================================================
        # 1, 2, 3, 4, 5, 6, 7, 8. RAG Response Generation by Agent A
        # =============================================================
        rag_res = client.post(
            f"/ai/conversations/{conv_a_id}/rag",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"top_k": 5},
        )
        assert rag_res.status_code == 200, f"RAG failed: {rag_res.text}"
        rag_data = rag_res.json()

        assert rag_data["conversation_id"] == conv_a_id
        assert rag_data["ai_state"] == "responded"
        assert rag_data["message"]["sender_type"] == "ai"
        assert rag_data["message"]["sender_user_id"] is None
        assert len(rag_data["sources"]) > 0

        # Verify source metadata and workspace isolation
        citation = rag_data["sources"][0]
        assert citation["document_id"] == doc_a_id
        assert citation["document_title"] == "Refund and Cancellation Policy"
        assert "refund" in citation["content"].lower()
        assert citation["relevance_score"] is not None

        # Verify database conversation state
        db.expire_all()
        conv_db = db.query(Conversation).filter(Conversation.id == conv_a_id).first()
        assert conv_db.ai_state == "responded"

        # =============================================================
        # 9. Cross-workspace conversation returns 404
        # =============================================================
        cross_rag = client.post(
            f"/ai/conversations/{conv_b_id}/rag",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_rag.status_code == 404

        # =============================================================
        # 10. Cross-workspace knowledge is NOT retrieved in Workspace A RAG
        # =============================================================
        msg_secret = Message(
            conversation_id=uuid.UUID(conv_a_id),
            sender_type=MessageSenderType.CUSTOMER,
            sender_user_id=None,
            content="What is the secret security code?",
        )
        db.add(msg_secret)
        db.commit()

        rag_secret_res = client.post(
            f"/ai/conversations/{conv_a_id}/rag",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"top_k": 5},
        )
        assert rag_secret_res.status_code == 200
        secret_sources = rag_secret_res.json()["sources"]
        for s in secret_sources:
            assert s["document_id"] != doc_b_id
            assert "ALPHA-BETA-999" not in s["content"]

        # =============================================================
        # 11. AI-disabled conversation blocks RAG processing (400)
        # =============================================================
        client.patch(
            f"/ai/conversations/{conv_a_id}/toggle",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"ai_enabled": False},
        )
        disabled_rag = client.post(
            f"/ai/conversations/{conv_a_id}/rag",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert disabled_rag.status_code == 400
        assert "disabled" in disabled_rag.text.lower()

        # Re-enable AI
        client.patch(
            f"/ai/conversations/{conv_a_id}/toggle",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"ai_enabled": True},
        )

        # =============================================================
        # 12. Unauthenticated request returns 401
        # =============================================================
        assert client.post(f"/ai/conversations/{conv_a_id}/rag").status_code == 401

        # =============================================================
        # 13. Refresh token used as access token returns 401
        # =============================================================
        ref_rag = client.post(
            f"/ai/conversations/{conv_a_id}/rag",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert ref_rag.status_code == 401

        # =============================================================
        # 14. Inactive user is rejected
        # =============================================================
        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": False},
        )
        inactive_rag = client.post(
            f"/ai/conversations/{conv_a_id}/rag",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert inactive_rag.status_code in [400, 401, 403]

        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": True},
        )

        # =============================================================
        # 16. Provider failure: ai_state becomes "failed" & returns 502
        # =============================================================
        with patch("app.ai.providers.mock_provider.MockLLMProvider.generate_response", side_effect=Exception("LLM service unavailable")):
            failed_rag = client.post(
                f"/ai/conversations/{conv_a_id}/rag",
                headers={"Authorization": f"Bearer {owner_a_token}"},
            )
            assert failed_rag.status_code == 502
            db.expire_all()
            conv_after_fail = db.query(Conversation).filter(Conversation.id == conv_a_id).first()
            assert conv_after_fail.ai_state == "failed"

    finally:
        db.close()
