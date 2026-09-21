from uuid import UUID

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class AIRunTrace(BaseModel):
    __tablename__ = "ai_run_traces"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    intent_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    decision: Mapped[str] = mapped_column(
        String(50),
        default="ANSWER",
        nullable=False,
        index=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )

    tools_executed: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    retrieved_sources: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    workspace = relationship("Workspace")
    conversation = relationship("Conversation")
    message = relationship("Message")

    __table_args__ = (
        Index("ix_ai_run_traces_workspace_decision", "workspace_id", "decision"),
    )
