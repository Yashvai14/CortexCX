from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.conversation.message_model import MessageSenderType
from app.conversation.model import ConversationStatus


class ConversationCreateRequest(BaseModel):
    customer_id: UUID
    subject: str = Field(
        min_length=1,
        max_length=255,
    )


class ConversationUpdateRequest(BaseModel):
    subject: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    status: ConversationStatus | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    subject: str
    status: ConversationStatus
    ai_enabled: bool = True
    ai_state: str = "idle"
    created_at: datetime
    updated_at: datetime


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    sender_type: MessageSenderType = MessageSenderType.AGENT


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    sender_type: MessageSenderType
    sender_user_id: UUID | None = None
    content: str
    created_at: datetime
