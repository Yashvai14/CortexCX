"""Contracts of the intent-routing layer.

The router answers one question for every customer message: which processing path is appropriate?

    DIRECT    conversational reply (no retrieval, no business data)
    RAG       company knowledge is required -> hybrid retrieval + grounded generation
    TOOLS     live business data (orders, stock, prices, coupons, refund status) -> store systems
    ESCALATE  a person must handle this (explicit request, dispute, sensitive account problem)
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Route(str, Enum):
    DIRECT = "DIRECT_CONVERSATION"   # ordinary conversation, corrections, small talk
    RAG = "RAG_KNOWLEDGE"            # company knowledge
    TOOLS = "BUSINESS_TOOL"          # live store data / authorised business workflow
    ESCALATE = "HUMAN_ESCALATION"    # a person must handle it
    CLARIFY = "CLARIFICATION"        # the message is ambiguous: ask, never escalate


class RouterIntent(str, Enum):
    # conversational
    GREETING = "GREETING"
    SMALL_TALK = "SMALL_TALK"
    COMPLIMENT = "COMPLIMENT"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    EMOTIONAL_RESPONSE = "EMOTIONAL_RESPONSE"
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    CORRECTION = "CORRECTION"            # "I didn't say anything", "that's not what I asked", "that's wrong"
    CONFUSION = "CONFUSION"              # "what do you mean?", "can you explain again?"
    APOLOGY = "APOLOGY"                  # the customer says sorry
    # company knowledge
    COMPANY_INFORMATION = "COMPANY_INFORMATION"
    PRODUCT_INFORMATION = "PRODUCT_INFORMATION"
    RETURN_POLICY = "RETURN_POLICY"
    REFUND_POLICY = "REFUND_POLICY"
    SHIPPING_POLICY = "SHIPPING_POLICY"
    CANCELLATION_POLICY = "CANCELLATION_POLICY"
    WARRANTY_POLICY = "WARRANTY_POLICY"
    PAYMENT_INFORMATION = "PAYMENT_INFORMATION"
    # live business data
    ORDER_INFORMATION = "ORDER_INFORMATION"
    # people
    ACCOUNT_SUPPORT = "ACCOUNT_SUPPORT"
    COMPLAINT = "COMPLAINT"
    HUMAN_SUPPORT_REQUEST = "HUMAN_SUPPORT_REQUEST"
    AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"


# Intents whose answer lives in the company's documents.
KNOWLEDGE_INTENTS = frozenset({
    RouterIntent.COMPANY_INFORMATION, RouterIntent.PRODUCT_INFORMATION, RouterIntent.RETURN_POLICY,
    RouterIntent.REFUND_POLICY, RouterIntent.SHIPPING_POLICY, RouterIntent.CANCELLATION_POLICY,
    RouterIntent.WARRANTY_POLICY, RouterIntent.PAYMENT_INFORMATION,
})

# Intent -> route when nothing else is known (the LLM disambiguation step validates against this table too).
DEFAULT_ROUTE: dict[RouterIntent, Route] = {
    RouterIntent.GREETING: Route.DIRECT,
    RouterIntent.SMALL_TALK: Route.DIRECT,
    RouterIntent.COMPLIMENT: Route.DIRECT,
    RouterIntent.ACKNOWLEDGEMENT: Route.DIRECT,
    RouterIntent.EMOTIONAL_RESPONSE: Route.DIRECT,
    RouterIntent.GENERAL_CONVERSATION: Route.DIRECT,
    RouterIntent.CORRECTION: Route.DIRECT,
    RouterIntent.CONFUSION: Route.DIRECT,
    RouterIntent.APOLOGY: Route.DIRECT,
    RouterIntent.ORDER_INFORMATION: Route.TOOLS,
    RouterIntent.HUMAN_SUPPORT_REQUEST: Route.ESCALATE,
    RouterIntent.AMBIGUOUS_QUERY: Route.CLARIFY,
    RouterIntent.COMPLAINT: Route.RAG,
    RouterIntent.ACCOUNT_SUPPORT: Route.RAG,
    **{i: Route.RAG for i in KNOWLEDGE_INTENTS},
}


class RoutingDecision(BaseModel):
    """Validated routing output. `source` records which stage produced it (rules / llm / default)."""

    intent: RouterIntent
    route: Route
    requires_retrieval: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    follow_up: bool = False          # continues the previous topic ("what about damaged products?")
    topic: RouterIntent | None = None  # the conversation topic this message belongs to
    source: str = "rules"

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    def log_fields(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value, "route": self.route.value, "router_confidence": round(self.confidence, 2),
            "router_source": self.source, "follow_up": self.follow_up,
        }


def decision(intent: RouterIntent, confidence: float, reason: str, *, route: Route | None = None,
             retrieval: bool | None = None, **extra: Any) -> RoutingDecision:
    """Build a decision with the route/retrieval flag implied by the intent unless overridden."""
    r = route or DEFAULT_ROUTE[intent]
    return RoutingDecision(
        intent=intent, route=r, requires_retrieval=(r == Route.RAG) if retrieval is None else retrieval,
        confidence=confidence, reason=reason, **extra,
    )
