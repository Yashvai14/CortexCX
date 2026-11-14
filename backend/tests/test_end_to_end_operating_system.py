import uuid
import app.database.models
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings

from app.commerce.model import Product, Inventory
from app.commerce.order_model import Order, OrderStatus
from app.commerce.policy_model import Policy
from app.database.database import SessionLocal
from app.knowledge.model import Document, DocumentChunk, KnowledgeSource, KnowledgeSourceType
from app.main import app
from app.workspace.model import Workspace

client = TestClient(app)


def test_complete_cortex_cx_operating_system():
    db: Session = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        password = "SecurePassword123!"

        # 1. Register Workspace and Owner
        reg_res = client.post(
            "/auth/register",
            json={
                "company_name": f"D2C Brand {suffix}",
                "company_slug": f"brand-{suffix}",
                "full_name": "Brand Owner",
                "email": f"owner_{suffix}@brand.com",
                "password": password,
            },
        )
        assert reg_res.status_code == 201
        owner_token = reg_res.json()["token"]["access_token"]
        ws_id = uuid.UUID(reg_res.json()["user"]["workspace_id"])

        headers = {"Authorization": f"Bearer {owner_token}"}

        # 2. Add Knowledge Base Source & Chunks (Shipping Policy)
        ks = KnowledgeSource(
            workspace_id=ws_id,
            name="Store Guide",
            source_type=KnowledgeSourceType.TXT,
        )
        db.add(ks)
        db.flush()

        doc = Document(
            workspace_id=ws_id,
            knowledge_source_id=ks.id,
            title="Shipping and Returns Guide",
            content="Standard delivery takes 3 to 5 business days.",
        )
        db.add(doc)
        db.flush()

        chunk = DocumentChunk(
            workspace_id=ws_id,
            document_id=doc.id,
            chunk_index=0,
            content="Standard domestic shipping arrives in 3 to 5 business days with FedEx tracking.",
            embedding=[0.1] * settings.EMBEDDING_DIMENSION,
        )
        db.add(chunk)

        # Add Commerce Policy
        pol = Policy(
            workspace_id=ws_id,
            policy_type="return",
            title="Return Policy",
            content="Returns accepted within 30 days of purchase for unused items.",
        )
        db.add(pol)

        # 3. Create Sample Product & Inventory via Commerce API
        prod_res = client.post(
            "/commerce/products",
            headers=headers,
            json={
                "sku": f"LUMEN-{suffix}",
                "name": "Lumen Glow Serum",
                "description": "Hydrating face serum with hyaluronic acid.",
                "price": 42.0,
                "category": "Skincare",
                "initial_stock": 25,
            },
        )
        assert prod_res.status_code == 201

        # Create Sample Customer & Order
        from app.customer.model import Customer, CustomerStatus
        cust = Customer(
            workspace_id=ws_id,
            full_name="Sarah Miller",
            email=f"sarah_{suffix}@example.com",
            status=CustomerStatus.ACTIVE,
        )
        db.add(cust)
        db.flush()

        order_num = f"ORD-{suffix.upper()}"
        order = Order(
            workspace_id=ws_id,
            customer_id=cust.id,
            order_number=order_num,
            status=OrderStatus.SHIPPED,
            total_amount=84.0,
            tracking_number=f"FDX-{suffix}",
            carrier="FedEx Express",
        )
        db.add(order)
        db.commit()

        # -------------------------------------------------------------
        # JOURNEY A: WebChat Customer Interaction
        # -------------------------------------------------------------
        webchat_res = client.post(
            "/channels/webchat/message",
            json={
                "workspace_id": str(ws_id),
                "session_id": f"sess_{suffix}",
                "content": "Hi! How many days does shipping take to arrive?",
                "customer_name": "Sarah Miller",
                "customer_email": f"sarah_{suffix}@example.com",
            },
        )
        assert webchat_res.status_code == 200
        webchat_data = webchat_res.json()
        assert webchat_data["decision"] in ("ANSWER", "ESCALATE")
        assert webchat_data["conversation_id"] is not None

        # Check WebChat History
        hist_res = client.get(
            f"/channels/webchat/history/sess_{suffix}?workspace_id={ws_id}"
        )
        assert hist_res.status_code == 200
        assert len(hist_res.json()["messages"]) >= 2

        # -------------------------------------------------------------
        # JOURNEY B: Telegram Order Tracking Webhook
        # -------------------------------------------------------------
        tg_headers = {}
        if settings.TELEGRAM_WEBHOOK_SECRET:
            tg_headers["X-Telegram-Bot-Api-Secret-Token"] = settings.TELEGRAM_WEBHOOK_SECRET
        tg_res = client.post(
            f"/channels/telegram/webhook?workspace_id={ws_id}",
            headers=tg_headers,
            json={
                "update_id": 999123,
                "message": {
                    "message_id": 1001,
                    "chat": {"id": 88776655},
                    "from": {"first_name": "Alex", "last_name": "Rider", "username": "alex_rider"},
                    "text": f"Can you track my order #{order_num} please?",
                },
            },
        )
        assert tg_res.status_code == 200
        assert tg_res.json()["status"] == "ok"

        # -------------------------------------------------------------
        # JOURNEY C: Human Escalation & Agent Assist Workflow
        # -------------------------------------------------------------
        # Send message requesting a human agent
        esc_trigger = client.post(
            "/channels/webchat/message",
            json={
                "workspace_id": str(ws_id),
                "session_id": f"sess_{suffix}",
                "content": "I demand to speak with a human support agent right now!",
            },
        )
        assert esc_trigger.status_code == 200
        assert esc_trigger.json()["escalated"] is True

        # Agent views open escalations
        escalations_res = client.get("/escalations", headers=headers)
        assert escalations_res.status_code == 200
        escalations = escalations_res.json()
        assert len(escalations) >= 1
        target_esc = escalations[0]
        esc_id = target_esc["id"]

        # Agent claims escalation
        claim_res = client.post(f"/escalations/{esc_id}/claim", headers=headers)
        assert claim_res.status_code == 200

        # Agent views Agent Assist detail
        detail_res = client.get(f"/escalations/{esc_id}", headers=headers)
        assert detail_res.status_code == 200
        assert "suggested_reply" in detail_res.json()

        # Agent responds and resolves escalation
        reply_res = client.post(
            f"/escalations/{esc_id}/respond",
            headers=headers,
            json={
                "content": "Hello! I am taking over this conversation to assist you personally.",
                "resolve": True,
            },
        )
        assert reply_res.status_code == 200

        # Submit Agent feedback for Learning Engine
        feedback_res = client.post(
            "/escalations/feedback",
            headers=headers,
            json={
                "conversation_id": target_esc["conversation_id"],
                "original_response": "AI initial attempt",
                "corrected_response": "Corrected policy instruction",
                "reason": "Clarified international shipping exception",
            },
        )
        assert feedback_res.status_code == 200

        # -------------------------------------------------------------
        # JOURNEY D: Analytics Overview Dashboard
        # -------------------------------------------------------------
        analytics_res = client.get("/analytics/overview", headers=headers)
        assert analytics_res.status_code == 200
        overview = analytics_res.json()
        assert overview["total_conversations"] >= 1
        assert "channels" in overview
        assert overview["channels"]["telegram"] >= 1 or overview["channels"]["webchat"] >= 1

    finally:
        db.close()
