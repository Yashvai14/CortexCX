from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.model import (
    DocumentStatus,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
)


class KnowledgeSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: KnowledgeSourceType = KnowledgeSourceType.TXT
    source_url: str | None = Field(None, max_length=1000)


class KnowledgeSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    source_type: KnowledgeSourceType
    source_url: str | None = None
    status: KnowledgeSourceStatus
    created_at: datetime
    updated_at: datetime


class DocumentCreateRequest(BaseModel):
    knowledge_source_id: UUID
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    filename: str | None = Field(None, max_length=255)
    metadata_json: dict | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    knowledge_source_id: UUID
    title: str
    filename: str | None = None
    content: str
    metadata_json: dict | None = None
    status: DocumentStatus
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    has_embedding: bool = False
    metadata_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    knowledge_source_id: UUID | None = None


class KnowledgeSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    knowledge_source_id: UUID | None = None
    content: str
    chunk_index: int
    similarity_score: float
    metadata_json: dict | None = None


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    results: list[KnowledgeSearchResult]
    total: int


class URLIngestRequest(BaseModel):
    knowledge_source_id: UUID
    url: str = Field(min_length=5, max_length=2000)
    title: str | None = Field(None, max_length=255)

