from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.tools.base import BaseTool, ToolResult
from app.commerce.services import (
    ProductService,
    OrderService,
    CouponService,
    PolicyService,
)


class ProductSearchTool(BaseTool):
    name = "product_search"
    description = "Search the product catalog by name, keywords, or category to find products, pricing, and stock."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or product name"},
            "category": {"type": "string", "description": "Optional category filter"},
            "limit": {"type": "integer", "description": "Max results to return (default 5)"},
        },
    }

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            query = kwargs.get("query")
            category = kwargs.get("category")
            limit = int(kwargs.get("limit", 5))

            products = ProductService.search_products(
                db=db,
                workspace_id=workspace_id,
                query=query,
                category=category,
                limit=limit,
            )
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=products,
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))


class OrderTrackingTool(BaseTool):
    name = "order_tracking"
    description = "Lookup shipping, tracking, and delivery status for a customer order by order number."
    parameters = {
        "type": "object",
        "properties": {
            "order_number": {"type": "string", "description": "The customer order number (e.g. ORD-1001 or #1001)"},
        },
        "required": ["order_number"],
    }

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            order_number = kwargs.get("order_number")
            if not order_number:
                return ToolResult(tool_name=self.name, success=False, error="order_number argument is required")

            # Identity context is injected by the planner/orchestrator (never taken from the model).
            # With no verified identity the tool discloses nothing about any order.
            customer_id = kwargs.get("_customer_id")
            emails = kwargs.get("_emails") or []
            order_info = OrderService.track_order_for_customer(
                db=db,
                workspace_id=workspace_id,
                order_number=str(order_number),
                customer_id=customer_id,
                verified_emails=emails,
            )
            if not order_info:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={
                        "found": False,
                        # No email on file in the conversation yet: ask for it. Otherwise the details
                        # didn't match; the same neutral answer covers "no such order" and "not yours".
                        "verification_required": not emails,
                        "message": f"No order found matching '{order_number}' for the verified details provided.",
                    },
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"found": True, "order": order_info},
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))


class InventoryTool(BaseTool):
    name = "inventory_lookup"
    description = "Check real-time stock availability, quantities, and low stock status for a SKU or product name."
    parameters = {
        "type": "object",
        "properties": {
            "sku_or_name": {"type": "string", "description": "Product SKU or product name to lookup stock for"},
        },
        "required": ["sku_or_name"],
    }

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            sku_or_name = kwargs.get("sku_or_name")
            if not sku_or_name:
                return ToolResult(tool_name=self.name, success=False, error="sku_or_name argument is required")

            inv = ProductService.get_inventory(
                db=db,
                workspace_id=workspace_id,
                sku_or_name=str(sku_or_name),
            )
            if not inv:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={"found": False, "message": f"Product '{sku_or_name}' not found in catalog."},
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"found": True, "inventory": inv},
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))


class CouponTool(BaseTool):
    name = "coupon_tool"
    description = "Validate a promo discount code or retrieve an active promotional discount for the customer."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Coupon code to validate"},
            "order_amount": {"type": "number", "description": "Subtotal amount of order in dollars"},
        },
    }

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            code = kwargs.get("code")
            order_amount = float(kwargs.get("order_amount", 0.0))

            if code:
                res = CouponService.validate_coupon(
                    db=db,
                    workspace_id=workspace_id,
                    code=str(code),
                    order_amount=order_amount,
                )
            else:
                res = CouponService.get_or_create_welcome_coupon(
                    db=db,
                    workspace_id=workspace_id,
                )
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=res,
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))


class RefundPolicyTool(BaseTool):
    name = "policy_lookup"
    description = "Lookup official store policies including returns, refunds, cancellations, warranty, and shipping."
    parameters = {
        "type": "object",
        "properties": {
            "policy_type": {
                "type": "string",
                "description": "Type of policy: 'return', 'refund', 'shipping', 'cancellation', 'warranty'",
            },
        },
        "required": ["policy_type"],
    }

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            policy_type = kwargs.get("policy_type", "return")
            pol = PolicyService.get_policy(
                db=db,
                workspace_id=workspace_id,
                policy_type=str(policy_type),
            )
            if not pol:
                # No official policy record. Never fabricate a "standard" policy: the answer must come from
                # the uploaded documents (retrieved separately) or not be given at all.
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={"found": False, "policy_type": policy_type,
                          "message": f"No official '{policy_type}' policy is on file."},
                )
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=pol,
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))
