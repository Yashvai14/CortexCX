from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class KnowledgeSourceType(str, Enum):
    TXT = "txt"
    PDF = "pdf"
    DOCX = "docx"
    WEBSITE = "website"


class KnowledgeSourceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeSource(BaseModel):
    __tablename__ = "knowledge_sources"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        SQLEnum(KnowledgeSourceType, name="knowledgesourcetype"),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    status: Mapped[KnowledgeSourceStatus] = mapped_column(
        SQLEnum(KnowledgeSourceStatus, name="knowledgesourcestatus"),
        default=KnowledgeSourceStatus.PENDING,
        nullable=False,
    )

    workspace = relationship(
        "Workspace",
    )

    documents = relationship(
        "Document",
        back_populates="knowledge_source",
        cascade="all, delete-orphan",
        order_by="Document.created_at.asc()",
    )

    __table_args__ = (
        Index(
            "ix_knowledge_sources_workspace_id_status",
            "workspace_id",
            "status",
        ),
    )


class Document(BaseModel):
    __tablename__ = "documents"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    knowledge_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="documentstatus"),
        default=DocumentStatus.COMPLETED,
        nullable=False,
    )

    knowledge_source = relationship(
        "KnowledgeSource",
        back_populates="documents",
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index.asc()",
    )

    __table_args__ = (
        Index(
            "ix_documents_workspace_id_knowledge_source_id",
            "workspace_id",
            "knowledge_source_id",
        ),
    )


class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    document = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
        Index(
            "ix_document_chunks_workspace_id_document_id",
            "workspace_id",
            "document_id",
        ),
    )
