from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class ChannelTypeEnum(str, Enum):
    TELEGRAM = "telegram"
    WEBCHAT = "webchat"
    INTERNAL = "internal"


class ChannelIncomingMessage(BaseModel):
    channel_type: ChannelTypeEnum
    channel_user_id: str = Field(description="Unique user/chat ID in the external channel (e.g. Telegram chat_id)")
    content: str
    customer_name: str | None = None
    customer_email: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelResponse(BaseModel):
    conversation_id: UUID
    content: str
    ai_state: str
    decision: str
    confidence_score: float
    sources: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    escalated: bool = False
