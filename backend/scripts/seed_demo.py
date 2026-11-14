"""Seed a workspace with realistic store data so the AI pipeline has real facts to ground on.

Usage (from backend/):  .venv/Scripts/python -m scripts.seed_demo <workspace-slug>
Idempotent: re-running skips anything that already exists.
"""
import sys
from datetime import datetime, timedelta, timezone

import app.database.models  # noqa: F401  (register all mappers)
from app.auth.model import User
from app.commerce.coupon_model import Coupon
from app.commerce.model import Inventory, Product
from app.commerce.order_model import Order, OrderItem, OrderStatus
from app.commerce.policy_model import Policy
from app.customer.model import Customer
from app.database.database import SessionLocal
from app.knowledge.commands.create_document import CreateDocumentCommand
from app.knowledge.commands.create_knowledge_source import CreateKnowledgeSourceCommand
from app.knowledge.commands.embed_document import EmbedDocumentCommand
from app.knowledge.model import Document, KnowledgeSource
from app.knowledge.schema import DocumentCreateRequest, KnowledgeSourceCreateRequest
from app.workspace.model import Workspace

PRODUCTS = [
    ("HOOD-BLU-M", "Classic Blue Hoodie", "Heavyweight 450gsm organic cotton fleece hoodie in navy blue. Relaxed fit, kangaroo pocket.", 59.0, "Apparel", 42),
    ("HOOD-BLK-L", "Midnight Black Hoodie", "Heavyweight organic cotton fleece hoodie in black. Relaxed fit.", 59.0, "Apparel", 3),
    ("TEE-WHT-M", "Everyday White Tee", "Soft 100% organic cotton crew-neck t-shirt. True to size.", 24.0, "Apparel", 120),
    ("SNK-RUN-42", "Aero Running Sneakers", "Lightweight breathable running sneakers with recycled-foam sole. EU size 42.", 89.0, "Footwear", 0),
    ("BOT-STL-750", "Insulated Steel Bottle 750ml", "Double-wall vacuum insulated bottle. Keeps drinks cold 24h or hot 12h. BPA-free.", 29.0, "Accessories", 64),
    ("TOTE-CVS-01", "Canvas Everyday Tote", "Sturdy natural canvas tote bag with inner zip pocket.", 19.0, "Accessories", 8),
]

POLICIES = [
    ("return", "Return Policy", "You can return unused items in original packaging within 30 days of delivery for a free exchange or refund. Start a return by sharing your order number; we email a prepaid label within one business day."),
    ("refund", "Refund Policy", "Approved refunds go back to your original payment method within 5 to 7 business days after we receive the return. Shipping fees are refunded only if the item arrived damaged or incorrect."),
    ("shipping", "Shipping Policy", "Standard shipping takes 3 to 5 business days and is free on orders over $50 (otherwise $4.99). Express shipping takes 1 to 2 business days for $12. We ship to the US, Canada and the UK."),
    ("cancellation", "Cancellation Policy", "Orders can be cancelled free of charge within 1 hour of placing them, or any time before they are marked as shipped."),
    ("warranty", "Warranty Policy", "All products carry a 12-month warranty against manufacturing defects. Normal wear and tear is not covered."),
]

KNOWLEDGE = {
    "Sizing and fit guide": (
        "Our hoodies and tees have a relaxed fit. If you are between sizes, choose the smaller size for a closer fit "
        "or the larger size for an oversized look. The Classic Blue Hoodie size M fits chest 38 to 40 inches. "
        "Sneakers run true to size; if you have wide feet we recommend going up half a size."
    ),
    "Care instructions": (
        "Machine wash cotton items cold with similar colours and tumble dry low. Do not bleach. "
        "Wash the insulated steel bottle by hand; it is not dishwasher safe. "
        "Wash canvas totes by hand with mild soap and air dry."
    ),
    "Payments and gift cards": (
        "We accept Visa, Mastercard, American Express, PayPal and Apple Pay. Digital gift cards are available from $25 "
        "to $200 and are delivered by email within minutes. Gift cards never expire."
    ),
    "Contact and support hours": (
        "Our support team is available Monday to Friday 9am to 6pm Eastern. Outside those hours our assistant can help "
        "with order tracking, stock, discounts and policies, and a teammate will reply the next business day."
    ),
}

CUSTOMERS = [
    ("Aarav Sharma", "aarav@example.com"),
    ("Maya Patel", "maya@example.com"),
]


def main(slug: str) -> None:
    db = SessionLocal()
    try:
        ws = db.query(Workspace).filter(Workspace.slug == slug).first()
        if not ws:
            sys.exit(f"Workspace '{slug}' not found")
        owner = db.query(User).filter(User.workspace_id == ws.id).order_by(User.created_at).first()

        # Products + inventory
        by_sku: dict[str, Product] = {}
        for sku, name, desc, price, cat, stock in PRODUCTS:
            p = db.query(Product).filter(Product.workspace_id == ws.id, Product.sku == sku).first()
            if not p:
                p = Product(workspace_id=ws.id, sku=sku, name=name, description=desc, price=price, category=cat)
                db.add(p)
                db.flush()
                db.add(Inventory(workspace_id=ws.id, product_id=p.id, quantity_available=stock))
            by_sku[sku] = p

        # Customers
        custs = []
        for full_name, email in CUSTOMERS:
            c = db.query(Customer).filter(Customer.workspace_id == ws.id, Customer.email == email).first()
            if not c:
                c = Customer(workspace_id=ws.id, full_name=full_name, email=email)
                db.add(c)
                db.flush()
            custs.append(c)

        # Orders
        now = datetime.now(timezone.utc)
        orders = [
            ("ORD-1001", custs[0], OrderStatus.SHIPPED, "BlueDart", "BD48271930", now + timedelta(days=2),
             [("HOOD-BLU-M", 1), ("TEE-WHT-M", 2)]),
            ("ORD-1002", custs[0], OrderStatus.PROCESSING, None, None, now + timedelta(days=5), [("BOT-STL-750", 1)]),
            ("ORD-1003", custs[1], OrderStatus.DELIVERED, "UPS", "1Z999AA10123456784", now - timedelta(days=3),
             [("SNK-RUN-42", 1)]),
        ]
        for number, cust, status, carrier, tracking, eta, items in orders:
            if db.query(Order).filter(Order.workspace_id == ws.id, Order.order_number == number).first():
                continue
            total = sum(by_sku[s].price * q for s, q in items)
            o = Order(
                workspace_id=ws.id, customer_id=cust.id, order_number=number, status=status,
                total_amount=total, carrier=carrier, tracking_number=tracking, estimated_delivery=eta,
            )
            db.add(o)
            db.flush()
            for s, q in items:
                db.add(OrderItem(workspace_id=ws.id, order_id=o.id, product_id=by_sku[s].id, quantity=q,
                                 unit_price=by_sku[s].price, total_price=by_sku[s].price * q))

        # Coupons
        coupons = [
            ("SAVE20", "percentage", 20.0, 50.0, None),
            ("FREESHIP", "fixed", 4.99, None, None),
            ("SUMMER10", "percentage", 10.0, None, now - timedelta(days=30)),
        ]
        for code, dtype, val, min_amt, until in coupons:
            if not db.query(Coupon).filter(Coupon.workspace_id == ws.id, Coupon.code == code).first():
                db.add(Coupon(workspace_id=ws.id, code=code, discount_type=dtype, discount_value=val,
                              min_order_amount=min_amt, valid_until=until, is_active=True))

        # Policies
        for ptype, title, content in POLICIES:
            if not db.query(Policy).filter(Policy.workspace_id == ws.id, Policy.policy_type == ptype).first():
                db.add(Policy(workspace_id=ws.id, policy_type=ptype, title=title, content=content, is_active=True))
        db.commit()

        # Knowledge base (chunked + embedded through the real commands)
        source = db.query(KnowledgeSource).filter(KnowledgeSource.workspace_id == ws.id,
                                                  KnowledgeSource.name == "Help Center").first()
        if not source:
            src = CreateKnowledgeSourceCommand.execute(db, owner, KnowledgeSourceCreateRequest(name="Help Center"))
            source_id = src.id
        else:
            source_id = source.id
        for title, content in KNOWLEDGE.items():
            if db.query(Document).filter(Document.workspace_id == ws.id, Document.title == title).first():
                continue
            doc = CreateDocumentCommand.execute(
                db, owner, DocumentCreateRequest(knowledge_source_id=source_id, title=title, content=content))
            EmbedDocumentCommand.execute(db, owner, doc.id)

        print(f"Seeded workspace '{slug}': {len(PRODUCTS)} products, {len(orders)} orders, "
              f"{len(coupons)} coupons, {len(POLICIES)} policies, {len(KNOWLEDGE)} knowledge docs.")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo-store")
