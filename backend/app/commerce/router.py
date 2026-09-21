from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.commerce.coupon_model import Coupon
from app.commerce.model import Inventory, Product
from app.commerce.order_model import Order, OrderItem, OrderStatus
from app.commerce.policy_model import Policy
from app.commerce.services import ProductService, OrderService, CouponService, PolicyService
from app.database.session import get_db

router = APIRouter(
    prefix="/commerce",
    tags=["E-Commerce Operations & Catalog"],
)


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    description: str | None = None
    price: float
    currency: str = "USD"
    category: str | None = None
    initial_stock: int = 10


class OrderCreateRequest(BaseModel):
    customer_id: UUID
    order_number: str
    total_amount: float
    carrier: str | None = "FedEx"
    tracking_number: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class CouponCreateRequest(BaseModel):
    code: str
    discount_type: str = "percentage"
    discount_value: float
    min_order_amount: float | None = None


class PolicyCreateRequest(BaseModel):
    policy_type: str
    title: str
    content: str


@router.get("/products")
def list_products(
    query: str | None = None,
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List and search products in the store catalog with stock levels."""
    return ProductService.search_products(
        db=db,
        workspace_id=current_user.workspace_id,
        query=query,
        category=category,
        limit=50,
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new catalog product with initial inventory."""
    prod = Product(
        workspace_id=current_user.workspace_id,
        sku=data.sku.strip(),
        name=data.name.strip(),
        description=data.description,
        price=data.price,
        currency=data.currency,
        category=data.category,
    )
    db.add(prod)
    db.flush()

    inv = Inventory(
        workspace_id=current_user.workspace_id,
        product_id=prod.id,
        quantity_available=data.initial_stock,
    )
    db.add(inv)
    db.commit()
    db.refresh(prod)
    return {"id": str(prod.id), "sku": prod.sku, "name": prod.name, "stock": data.initial_stock}


@router.get("/orders")
def list_orders(
    customer_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List workspace orders with customer and tracking status."""
    q = db.query(Order).filter(Order.workspace_id == current_user.workspace_id)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    orders = q.order_by(Order.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(o.id),
            "order_number": o.order_number,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "total_amount": o.total_amount,
            "tracking_number": o.tracking_number,
            "carrier": o.carrier,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create an order record for tracking and simulation."""
    order = Order(
        workspace_id=current_user.workspace_id,
        customer_id=data.customer_id,
        order_number=data.order_number.strip(),
        total_amount=data.total_amount,
        status=OrderStatus.SHIPPED,
        carrier=data.carrier,
        tracking_number=data.tracking_number,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": str(order.id), "order_number": order.order_number}


@router.get("/orders/{order_number}")
def track_order(
    order_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track an order by its number."""
    res = OrderService.track_order(
        db=db,
        workspace_id=current_user.workspace_id,
        order_number=order_number,
    )
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return res


@router.get("/coupons")
def list_coupons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List available promotional coupon codes."""
    coupons = (
        db.query(Coupon)
        .filter(Coupon.workspace_id == current_user.workspace_id)
        .all()
    )
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "discount_type": c.discount_type,
            "discount_value": c.discount_value,
            "is_active": c.is_active,
        }
        for c in coupons
    ]


@router.post("/coupons", status_code=status.HTTP_201_CREATED)
def create_coupon(
    data: CouponCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    coupon = Coupon(
        workspace_id=current_user.workspace_id,
        code=data.code.strip().upper(),
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        is_active=True,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"id": str(coupon.id), "code": coupon.code}


@router.get("/policies")
def list_policies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all workspace store policies."""
    policies = (
        db.query(Policy)
        .filter(Policy.workspace_id == current_user.workspace_id)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "policy_type": p.policy_type,
            "title": p.title,
            "content": p.content,
            "is_active": p.is_active,
        }
        for p in policies
    ]


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_policy(
    data: PolicyCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    policy = (
        db.query(Policy)
        .filter(
            Policy.workspace_id == current_user.workspace_id,
            Policy.policy_type == data.policy_type.strip().lower(),
        )
        .first()
    )
    if policy:
        policy.title = data.title.strip()
        policy.content = data.content.strip()
    else:
        policy = Policy(
            workspace_id=current_user.workspace_id,
            policy_type=data.policy_type.strip().lower(),
            title=data.title.strip(),
            content=data.content.strip(),
            is_active=True,
        )
        db.add(policy)

    db.commit()
    db.refresh(policy)
    return {"id": str(policy.id), "policy_type": policy.policy_type, "title": policy.title}
