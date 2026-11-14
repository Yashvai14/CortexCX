from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.intent.schema import IntentEnum, IntentResult
from app.ai.planner.schema import PlanResult, PlanStep
from app.ai.tools.base import ToolResult
from app.ai.tools.registry import tool_registry


class ExecutedPlan:
    def __init__(
        self,
        plan: PlanResult,
        tool_results: list[ToolResult],
    ):
        self.plan = plan
        self.tool_results = tool_results

    @property
    def has_errors(self) -> bool:
        return any(not r.success for r in self.tool_results)

    @property
    def summary_context(self) -> str:
        if not self.tool_results:
            return ""
        from app.ai.facts import render_facts

        return render_facts(self.tool_results)


class AIPlanner:
    """Plans and executes task steps based on detected intent, entities, and context."""

    @classmethod
    def create_plan(
        cls,
        query: str,
        intent: IntentResult,
        memories: list[str] | None = None,
    ) -> PlanResult:
        # 1. Immediate escalation checks
        if intent.intent == IntentEnum.HUMAN_AGENT:
            return PlanResult(
                goal="Escalate to human support agent",
                steps=[],
                requires_rag=False,
                escalate=True,
                escalation_reason="Customer explicitly requested human assistance.",
            )

        if intent.intent == IntentEnum.COMPLAINT and intent.confidence >= 0.90:
            # Check for severe complaint keywords
            lower = query.lower()
            if any(w in lower for w in ["unacceptable", "scam", "lawyer", "terrible", "fraud"]):
                return PlanResult(
                    goal="Escalate severe customer complaint to human manager",
                    steps=[],
                    requires_rag=False,
                    escalate=True,
                    escalation_reason="Severe customer complaint detected.",
                )

        steps: list[PlanStep] = []
        requires_rag = False

        # Documents are always consulted for informational questions; only live-data lookups with everything
        # they need (an order number, a coupon code) and plain greetings skip retrieval.
        requires_rag = not intent.entities.get("smalltalk") and intent.intent not in (
            IntentEnum.ORDER_STATUS, IntentEnum.ORDER_CANCELLATION, IntentEnum.HUMAN_AGENT,
        )

        # 2. Map intents to appropriate tools
        if intent.intent == IntentEnum.ORDER_STATUS:
            order_num = intent.entities.get("order_number")
            if order_num:
                steps.append(
                    PlanStep(
                        tool_name="order_tracking",
                        arguments={"order_number": order_num},
                        description=f"Track shipping and delivery status for order {order_num}",
                    )
                )
            else:
                # No order number yet: the right move is to ask for it, not to search the knowledge base.
                requires_rag = False

        elif intent.intent == IntentEnum.ORDER_CANCELLATION:
            order_num = intent.entities.get("order_number")
            if order_num:
                steps.append(
                    PlanStep(
                        tool_name="order_tracking",
                        arguments={"order_number": order_num},
                        description=f"Check order status to evaluate cancellation eligibility for {order_num}",
                    )
                )
            steps.append(
                PlanStep(
                    tool_name="policy_lookup",
                    arguments={"policy_type": "cancellation"},
                    description="Check order cancellation policy terms",
                )
            )

        elif intent.intent in (IntentEnum.PRODUCT_SEARCH, IntentEnum.PRODUCT_INFORMATION):
            steps.append(
                PlanStep(
                    tool_name="product_search",
                    arguments={
                        "query": query,
                        "category": intent.entities.get("category"),
                        "limit": 5,
                    },
                    description=f"Search catalog for matching products: '{query}'",
                )
            )

        elif intent.intent == IntentEnum.INVENTORY:
            sku_or_name = intent.entities.get("product_name") or query
            steps.append(
                PlanStep(
                    tool_name="inventory_lookup",
                    arguments={"sku_or_name": sku_or_name},
                    description=f"Check real-time stock levels for '{sku_or_name}'",
                )
            )

        elif intent.intent in (IntentEnum.COUPON, IntentEnum.DISCOUNT):
            code = intent.entities.get("code")
            steps.append(
                PlanStep(
                    tool_name="coupon_tool",
                    arguments={"code": code} if code else {},
                    description="Validate promotional coupon code or retrieve welcome offer",
                )
            )

        elif intent.intent in (IntentEnum.POLICY, IntentEnum.REFUND, IntentEnum.RETURN, IntentEnum.DELIVERY):
            pol_type = intent.entities.get("policy_type")
            if not pol_type:
                if intent.intent == IntentEnum.REFUND:
                    pol_type = "refund"
                elif intent.intent == IntentEnum.RETURN:
                    pol_type = "return"
                elif intent.intent == IntentEnum.DELIVERY:
                    pol_type = "shipping"
                else:
                    # A generic "what is your policy on X?" names no known policy type. Do NOT default to the return
                    # policy: that would present an unrelated policy as the answer. The document search decides.
                    pol_type = None

            if pol_type:
                steps.append(
                    PlanStep(
                        tool_name="policy_lookup",
                        arguments={"policy_type": pol_type},
                        description=f"Retrieve official store policy for {pol_type}",
                    )
                )
            # Complement policy lookup with knowledge search for nuanced FAQs
            requires_rag = True

        elif intent.intent == IntentEnum.GENERAL_FAQ:
            requires_rag = True

        else:
            # For OTHER or unclassified, try knowledge search (not for plain greetings / thanks)
            requires_rag = not intent.entities.get("smalltalk")

        return PlanResult(
            goal=f"Resolve customer inquiry: {intent.intent.value}",
            steps=steps,
            requires_rag=requires_rag,
            escalate=False,
        )

    @classmethod
    def execute_plan(
        cls,
        db: Session,
        workspace_id: UUID,
        plan: PlanResult,
        context: dict[str, Any] | None = None,
    ) -> ExecutedPlan:
        """Run the planned tools. `context` carries trusted identity (`_customer_id`, `_emails`)
        that tools use for authorization; it overrides anything in a step's own arguments."""
        tool_results: list[ToolResult] = []
        for step in plan.steps:
            res = tool_registry.execute_tool(
                tool_name=step.tool_name,
                db=db,
                workspace_id=workspace_id,
                arguments={**step.arguments, **(context or {})},
            )
            tool_results.append(res)

        return ExecutedPlan(plan=plan, tool_results=tool_results)
