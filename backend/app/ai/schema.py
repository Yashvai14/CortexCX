from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.conversation.schema import MessageResponse


class AIProcessConversationRequest(BaseModel):
    prompt_override: str | None = None


class AIProcessConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID
    message: MessageResponse
    ai_state: str
    provider: str


class AIToggleRequest(BaseModel):
    ai_enabled: bool


class AIConversationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID
    ai_enabled: bool
    ai_state: str
    total_ai_messages: int
    last_processed_at: datetime | None = None
