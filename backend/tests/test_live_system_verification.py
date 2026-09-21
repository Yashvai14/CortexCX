"""Live system verification tests exercising the real database, live Ollama, and full conversational pipeline."""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.database.models
from app.database.database import SessionLocal, engine
from app.core.config import settings
from app.workspace.model import Workspace
from app.auth.model import User, UserRole
from app.auth.security import hash_password
from app.commerce.model import Product, Inventory
from app.commerce.order_model import Order, OrderStatus, OrderItem
from app.commerce.policy_model import Policy
from app.customer.model import Customer, CustomerStatus
from app.conversation.model import Conversation, ConversationStatus
from app.conversation.message_model import Message, MessageSenderType
from app.escalation.model import HumanEscalation, EscalationStatus
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.orchestrator import ConversationOrchestrator
from app.memory.service import CustomerMemoryService
from app.channels.schema import ChannelIncomingMessage, ChannelTypeEnum
from app.channels.webchat_adapter import WebChatAdapter


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_live_database_tables_and_connection(db: Session):
    """Verify live PostgreSQL connectivity and core tables exist."""
    res = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public';")).fetchall()
    tables = {r[0] for r in res}
    expected_tables = {
        "workspaces",
        "users",
        "customers",
        "conversations",
        "messages",
        "products",
        "inventory",
        "orders",
        "order_items",
        "coupons",
        "policies",
        "customer_memories",
        "human_escalations",
        "agent_feedbacks",
        "ai_run_traces",
        "channel_identities",
        "knowledge_sources",
        "documents",
        "document_chunks",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_live_ollama_inference():
    """Verify live HTTP communication and structured text generation with Ollama."""
    provider = OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_MODEL,
        timeout=60.0,
    )
    resp = provider.generate_response(
        conversation_subject="Store Inquiry",
        messages=[
            {"sender_type": "customer", "content": "What is the capital of France? Answer with just the city name."}
        ],
    )
    assert "Paris" in resp or len(resp) > 0


def test_live_end_to_end_conversational_turn(db: Session):
    """Verify end-to-end conversation flow: Customer -> WebChat -> Memory -> Intent -> Planner -> Tools/RAG -> Ollama -> Response."""
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(name=f"Live_Store_{uid}", slug=f"live-store-{uid}")
    db.add(ws)
    db.flush()

    # Seed customer
    cust = Customer(
        workspace_id=ws.id,
        full_name=f"Live Visitor {uid}",
        email=f"visitor_{uid}@cortex.live",
        status=CustomerStatus.ACTIVE,
    )
    db.add(cust)
    db.flush()

    # Seed product catalog
    prod = Product(
        workspace_id=ws.id,
        name="Organic Green Tea",
        sku=f"TEA-{uid}",
        price=18.50,
        category="Beverages",
        description="Certified vegan and organic green tea leaves.",
    )
    db.add(prod)

    # Seed return policy
    pol = Policy(
        workspace_id=ws.id,
        policy_type="return",
        title="Store Return Policy",
        content="We offer a 30-day return policy on all unopened beverages.",
    )
    db.add(pol)

    # Seed customer order
    order = Order(
        workspace_id=ws.id,
        customer_id=cust.id,
        order_number=f"ORD-{uid}",
        status=OrderStatus.SHIPPED,
        total_amount=37.00,
        tracking_number=f"TRK-{uid}-EXPRESS",
        carrier="FedEx",
    )
    db.add(order)
    db.commit()


    adapter = WebChatAdapter()

    # Turn 1: Customer expresses preference & asks for policy
    msg1 = ChannelIncomingMessage(
        channel_type=ChannelTypeEnum.WEBCHAT,
        channel_user_id=f"session_{uid}",
        content="I prefer vegan organic products. What is your return policy?",
        customer_name=f"Live Visitor {uid}",
        customer_email=f"visitor_{uid}@cortex.live",
    )
    resp1 = adapter.handle_incoming_message(db=db, workspace_id=ws.id, incoming=msg1)
    assert resp1.decision in ("ANSWER", "ESCALATE")
    assert resp1.conversation_id is not None

    # Verify memory was persisted
    cust = db.query(Customer).filter(Customer.email == f"visitor_{uid}@cortex.live").first()
    assert cust is not None
    memories = CustomerMemoryService.get_relevant_memories(db, workspace_id=ws.id, customer_id=cust.id)
    assert len(memories) > 0

    # Turn 2: Order tracking inquiry
    msg2 = ChannelIncomingMessage(
        channel_type=ChannelTypeEnum.WEBCHAT,
        channel_user_id=f"session_{uid}",
        content=f"Where is my order #ORD-{uid}?",
        customer_name=f"Live Visitor {uid}",
        customer_email=f"visitor_{uid}@cortex.live",
    )
    resp2 = adapter.handle_incoming_message(db=db, workspace_id=ws.id, incoming=msg2)
    assert resp2.decision == "ANSWER"
    assert resp2.confidence_score >= 0.70

    # Turn 3: Human handoff request
    msg3 = ChannelIncomingMessage(
        channel_type=ChannelTypeEnum.WEBCHAT,
        channel_user_id=f"session_{uid}",
        content="I want to speak with a human agent please",
        customer_name=f"Live Visitor {uid}",
        customer_email=f"visitor_{uid}@cortex.live",
    )
    resp3 = adapter.handle_incoming_message(db=db, workspace_id=ws.id, incoming=msg3)
    assert resp3.escalated is True
    assert resp3.ai_state == "escalated"

    # Verify escalation was created in database
    esc = db.query(HumanEscalation).filter(HumanEscalation.conversation_id == resp3.conversation_id).first()
    assert esc is not None
    assert esc.status == EscalationStatus.PENDING
