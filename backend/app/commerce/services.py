from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.commerce.model import Product, Inventory
from app.commerce.order_model import Order, OrderItem, OrderStatus
from app.commerce.coupon_model import Coupon
from app.commerce.policy_model import Policy


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
        if query:
            pattern = f"%{query.strip()}%"
            q = q.filter(
                (Product.name.ilike(pattern)) | (Product.description.ilike(pattern)) | (Product.sku.ilike(pattern))
            )

        products = q.limit(limit).all()
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
        order = (
            db.query(Order)
            .filter(
                Order.workspace_id == workspace_id,
                (Order.order_number.ilike(clean_num)) | (Order.order_number.ilike(f"%{clean_num}%")),
            )
            .first()
        )
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
