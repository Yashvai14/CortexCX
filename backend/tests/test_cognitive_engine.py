import uuid
import app.database.models
from sqlalchemy.orm import Session

from app.ai.confidence import ConfidenceEvaluator, DecisionEnum
from app.ai.intent import IntentClassifier, IntentEnum
from app.ai.planner import AIPlanner
from app.ai.tools import tool_registry
from app.commerce.model import Product, Inventory
from app.commerce.order_model import Order, OrderStatus
from app.commerce.coupon_model import Coupon
from app.commerce.policy_model import Policy
from app.database.database import SessionLocal
from app.workspace.model import Workspace


def test_intent_detection():
    # Order tracking
    res_order = IntentClassifier.classify("Where is my order #ORD-9982? Can you track it?")
    assert res_order.intent == IntentEnum.ORDER_STATUS
    assert res_order.confidence >= 0.8
    assert res_order.entities.get("order_number") == "ORD-9982"

    # Human agent
    res_human = IntentClassifier.classify("I want to speak with a human agent please")
    assert res_human.intent == IntentEnum.HUMAN_AGENT
    assert res_human.confidence >= 0.9

    # Return / Refund
    res_refund = IntentClassifier.classify("What is your refund policy? How do I return a damaged shirt?")
    assert res_refund.intent in (IntentEnum.REFUND, IntentEnum.RETURN, IntentEnum.POLICY)
    assert res_refund.confidence >= 0.8

    # Coupon
    res_coupon = IntentClassifier.classify("Do you have any discount code or coupon available?")
    assert res_coupon.intent in (IntentEnum.COUPON, IntentEnum.DISCOUNT)


def test_commerce_tools_and_planner():
    db: Session = SessionLocal()
    try:
        ws_id = uuid.uuid4()
        ws = Workspace(id=ws_id, name=f"Test Commerce {ws_id.hex[:6]}", slug=f"ws-{ws_id.hex[:6]}")
        db.add(ws)

        # Add sample product and inventory
        prod = Product(
            workspace_id=ws_id,
            sku="SKU-SHIRT-01",
            name="Classic Cotton T-Shirt",
            description="100% organic cotton t-shirt in midnight black.",
            price=29.99,
            category="Apparel",
        )
        db.add(prod)
        db.flush()

        inv = Inventory(
            workspace_id=ws_id,
            product_id=prod.id,
            quantity_available=45,
            low_stock_threshold=5,
        )
        db.add(inv)

        # Add sample customer
        from app.customer.model import Customer, CustomerStatus
        cust = Customer(
            workspace_id=ws_id,
            full_name="John Doe",
            email=f"john_{ws_id.hex[:6]}@example.com",
            status=CustomerStatus.ACTIVE,
        )
        db.add(cust)
        db.flush()

        # Add sample order
        order = Order(
            workspace_id=ws_id,
            customer_id=cust.id,
            order_number="ORD-7744",
            status=OrderStatus.SHIPPED,
            total_amount=59.98,
            tracking_number="TRACK-123456",
            carrier="FedEx",
        )
        db.add(order)

        # Add sample policy
        pol = Policy(
            workspace_id=ws_id,
            policy_type="refund",
            title="30-Day Hassle-Free Refund",
            content="Items can be refunded within 30 days of delivery.",
        )
        db.add(pol)
        db.commit()

        # 1. Test Product Search Tool
        prod_res = tool_registry.execute_tool(
            "product_search",
            db=db,
            workspace_id=ws_id,
            arguments={"query": "Cotton"},
        )
        assert prod_res.success is True
        assert len(prod_res.data) >= 1
        assert prod_res.data[0]["sku"] == "SKU-SHIRT-01"

        # 2. Test Order Tracking Tool
        order_res = tool_registry.execute_tool(
            "order_tracking",
            db=db,
            workspace_id=ws_id,
            arguments={"order_number": "ORD-7744"},
        )
        # Without a verified identity the tool must disclose nothing.
        assert order_res.data["found"] is False
        assert order_res.data["verification_required"] is True
        assert "FedEx" not in str(order_res.data)

        order_res = tool_registry.execute_tool(
            "order_tracking",
            db=db,
            workspace_id=ws_id,
            arguments={"order_number": "ORD-7744", "_emails": [cust.email]},
        )
        assert order_res.success is True
        assert order_res.data["found"] is True
        assert order_res.data["order"]["carrier"] == "FedEx"

        # 3. Test Inventory Lookup Tool
        inv_res = tool_registry.execute_tool(
            "inventory_lookup",
            db=db,
            workspace_id=ws_id,
            arguments={"sku_or_name": "SKU-SHIRT-01"},
        )
        assert inv_res.success is True
        assert inv_res.data["inventory"]["quantity_available"] == 45

        # 4. Test Policy Lookup Tool
        pol_res = tool_registry.execute_tool(
            "policy_lookup",
            db=db,
            workspace_id=ws_id,
            arguments={"policy_type": "refund"},
        )
        assert pol_res.success is True
        assert "30 days" in pol_res.data["content"]

        # 5. Test AI Planner
        intent_res = IntentClassifier.classify("Where is my order ORD-7744?")
        plan = AIPlanner.create_plan(query="Where is my order ORD-7744?", intent=intent_res)
        assert len(plan.steps) >= 1
        assert plan.steps[0].tool_name == "order_tracking"

        executed = AIPlanner.execute_plan(
            db=db, workspace_id=ws_id, plan=plan, context={"_customer_id": cust.id, "_emails": []}
        )
        assert executed.has_errors is False
        assert len(executed.tool_results) >= 1
        assert "FedEx" in executed.summary_context

        # 6. Test Confidence Evaluator
        confidence = ConfidenceEvaluator.evaluate(
            intent=intent_res,
            executed_plan=executed,
            threshold=0.75,
        )
        assert confidence.decision == DecisionEnum.ANSWER
        assert confidence.confidence_score >= 0.75

        # Test Escalation Trigger
        human_intent = IntentClassifier.classify("I need to speak to a real person right now")
        human_plan = AIPlanner.create_plan(query="human", intent=human_intent)
        assert human_plan.escalate is True
        human_confidence = ConfidenceEvaluator.evaluate(intent=human_intent)
        assert human_confidence.decision == DecisionEnum.ESCALATE

    finally:
        db.close()
