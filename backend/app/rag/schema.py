from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.conversation.schema import MessageResponse


class RAGProcessRequest(BaseModel):
    top_k: int = Field(5, ge=1, le=20)
    prompt_override: str | None = None
    max_history_messages: int = Field(10, ge=1, le=50)


class RAGSourceCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    knowledge_source_id: UUID | None = None
    document_title: str | None = None
    relevance_score: float
    content: str
    metadata_json: dict | None = None


class RAGProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID
    message: MessageResponse
    ai_state: str
    provider: str
    sources: list[RAGSourceCitation]
