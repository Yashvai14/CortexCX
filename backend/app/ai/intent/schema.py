from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class IntentEnum(str, Enum):
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    PRODUCT_INFORMATION = "PRODUCT_INFORMATION"
    ORDER_STATUS = "ORDER_STATUS"
    ORDER_CANCELLATION = "ORDER_CANCELLATION"
    REFUND = "REFUND"
    RETURN = "RETURN"
    COUPON = "COUPON"
    DISCOUNT = "DISCOUNT"
    INVENTORY = "INVENTORY"
    DELIVERY = "DELIVERY"
    POLICY = "POLICY"
    GENERAL_FAQ = "GENERAL_FAQ"
    HUMAN_AGENT = "HUMAN_AGENT"
    COMPLAINT = "COMPLAINT"
    OTHER = "OTHER"


class IntentResult(BaseModel):
    intent: IntentEnum = Field(description="The primary classified intent of the customer message")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score of classification between 0 and 1")
    entities: dict[str, Any] = Field(default_factory=dict, description="Extracted key entities (e.g., order_number, product_name, coupon_code)")
    reasoning: str = Field(default="", description="Brief explanation for the classified intent")
