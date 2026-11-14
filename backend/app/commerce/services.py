from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.commerce.model import Product, Inventory
from app.commerce.order_model import Order, OrderItem, OrderStatus
from app.commerce.coupon_model import Coupon
from app.commerce.policy_model import Policy
from app.ai.text_utils import keywords, stem


class ProductService:
    @staticmethod
    def search_products(
        db: Session,
        workspace_id: UUID,
        query: str | None = None,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        q = db.query(Product).filter(
            Product.workspace_id == workspace_id,
            Product.is_active.is_(True),
        )
        if category:
            q = q.filter(Product.category.ilike(f"%{category.strip()}%"))
        products = q.all()
        if query and query.strip():
            # Match on informative keywords (not the whole sentence) and rank by how many hit.
            terms = [stem(t) for t in keywords(query, 6)]
            if terms:
                scored = []
                for p in products:
                    hay = " ".join(filter(None, [p.name, p.description, p.sku, p.category])).lower()
                    name = p.name.lower()
                    hits = sum(1 for t in terms if t in hay)
                    if hits:
                        scored.append((hits + 0.5 * sum(1 for t in terms if t in name), p))
                scored.sort(key=lambda x: x[0], reverse=True)
                products = [p for _, p in scored]
            else:
                products = []
        products = products[:limit]
        results = []
        for p in products:
            inv = db.query(Inventory).filter(Inventory.product_id == p.id).first()
            qty = inv.quantity_available if inv else 0
            results.append({
                "id": str(p.id),
                "sku": p.sku,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "currency": p.currency,
                "category": p.category,
                "in_stock": qty > 0,
                "quantity_available": qty,
            })
        return results

    @staticmethod
    def get_inventory(
        db: Session,
        workspace_id: UUID,
        sku_or_name: str,
    ) -> dict | None:
        p = (
            db.query(Product)
            .filter(
                Product.workspace_id == workspace_id,
                (Product.sku.ilike(sku_or_name.strip())) | (Product.name.ilike(f"%{sku_or_name.strip()}%")),
            )
            .first()
        )
        if not p:
            # The input is usually a whole sentence; fall back to the best keyword match.
            found = ProductService.search_products(db=db, workspace_id=workspace_id, query=sku_or_name, limit=1)
            if not found:
                return None
            p = db.query(Product).filter(Product.id == found[0]["id"]).first()
            if not p:
                return None

        inv = db.query(Inventory).filter(Inventory.product_id == p.id).first()
        qty = inv.quantity_available if inv else 0
        return {
            "product_id": str(p.id),
            "sku": p.sku,
            "product_name": p.name,
            "quantity_available": qty,
            "in_stock": qty > 0,
            "low_stock": qty <= (inv.low_stock_threshold if inv else 5),
        }


class OrderService:
    @staticmethod
    def track_order(
        db: Session,
        workspace_id: UUID,
        order_number: str,
    ) -> dict | None:
        clean_num = order_number.strip().replace("#", "")
        base = db.query(Order).filter(Order.workspace_id == workspace_id)
        # Exact match first; only fall back to a suffix match for a reasonably specific reference
        # (e.g. "1001" -> "ORD-1001"), never a loose substring of a short token.
        order = base.filter(Order.order_number.ilike(clean_num)).first()
        if not order and len(clean_num) >= 4 and any(c.isdigit() for c in clean_num):
            order = base.filter(Order.order_number.ilike(f"%{clean_num}")).first()
        if not order:
            return None

        items = []
        for item in order.items:
            items.append({
                "product_name": item.product.name if item.product else "Item",
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            })

        status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
        return {
            "order_number": order.order_number,
            "status": status_val,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "tracking_number": order.tracking_number,
            "carrier": order.carrier,
            "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "items": items,
        }

    @staticmethod
    def track_order_for_customer(
        db: Session,
        workspace_id: UUID,
        order_number: str,
        customer_id: UUID | None = None,
        verified_emails: list[str] | None = None,
    ) -> dict | None:
        """Order details for an AI/customer-facing channel, only if the requester owns the order.

        Ownership = the order belongs to the conversation's customer, OR the requester supplied the
        email address on the order. Returns None for "not found" and "not yours" alike so the
        response never reveals whether someone else's order number exists.
        """
        info = OrderService.track_order(db=db, workspace_id=workspace_id, order_number=order_number)
        if not info:
            return None
        order = (
            db.query(Order)
            .filter(Order.workspace_id == workspace_id, Order.order_number == info["order_number"])
            .first()
        )
        if not order:
            return None
        if customer_id and order.customer_id == customer_id:
            return info
        owner_email = (order.customer.email or "").strip().lower() if order.customer else ""
        if owner_email and owner_email in {e.strip().lower() for e in (verified_emails or [])}:
            return info
        return None

    @staticmethod
    def list_customer_orders(
        db: Session,
        workspace_id: UUID,
        customer_id: UUID,
        limit: int = 5,
    ) -> list[dict]:
        orders = (
            db.query(Order)
            .filter(
                Order.workspace_id == workspace_id,
                Order.customer_id == customer_id,
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "order_number": o.order_number,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "total_amount": o.total_amount,
                "currency": o.currency,
                "tracking_number": o.tracking_number,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]


class CouponService:
    @staticmethod
    def validate_coupon(
        db: Session,
        workspace_id: UUID,
        code: str,
        order_amount: float = 0.0,
    ) -> dict:
        coupon = (
            db.query(Coupon)
            .filter(
                Coupon.workspace_id == workspace_id,
                Coupon.code.ilike(code.strip()),
                Coupon.is_active.is_(True),
            )
            .first()
        )
        if not coupon:
            return {"valid": False, "reason": f"Coupon '{code}' does not exist or is inactive."}

        if coupon.valid_until and coupon.valid_until < datetime.now(coupon.valid_until.tzinfo):
            return {"valid": False, "reason": f"Coupon '{code}' has expired."}

        if coupon.max_uses and coupon.uses_count >= coupon.max_uses:
            return {"valid": False, "reason": f"Coupon '{code}' usage limit has been reached."}

        if coupon.min_order_amount and order_amount < coupon.min_order_amount:
            return {
                "valid": False,
                "reason": f"Minimum order amount of ${coupon.min_order_amount:.2f} required for coupon '{code}'.",
            }

        return {
            "valid": True,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "description": f"{coupon.discount_value}% off" if coupon.discount_type == "percentage" else f"${coupon.discount_value} off",
        }

    @staticmethod
    def get_or_create_welcome_coupon(
        db: Session,
        workspace_id: UUID,
        discount_percent: float = 10.0,
    ) -> dict:
        code = f"WELCOME{int(discount_percent)}"
        coupon = (
            db.query(Coupon)
            .filter(
                Coupon.workspace_id == workspace_id,
                Coupon.code == code,
            )
            .first()
        )
        if not coupon:
            coupon = Coupon(
                workspace_id=workspace_id,
                code=code,
                discount_type="percentage",
                discount_value=discount_percent,
                is_active=True,
            )
            db.add(coupon)
            db.commit()
            db.refresh(coupon)

        return {
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
        }


class PolicyService:
    @staticmethod
    def get_policy(
        db: Session,
        workspace_id: UUID,
        policy_type: str,
    ) -> dict | None:
        policy = (
            db.query(Policy)
            .filter(
                Policy.workspace_id == workspace_id,
                Policy.policy_type.ilike(f"%{policy_type.strip()}%"),
                Policy.is_active.is_(True),
            )
            .first()
        )
        if not policy:
            return None

        return {
            "policy_type": policy.policy_type,
            "title": policy.title,
            "content": policy.content,
        }
