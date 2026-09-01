from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Conversation(BaseModel):
    __tablename__ = "conversations"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus, name="conversationstatus"),
        default=ConversationStatus.OPEN,
        nullable=False,
    )

    ai_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    ai_state: Mapped[str] = mapped_column(
        String(50),
        default="idle",
        nullable=False,
    )

    workspace = relationship(
        "Workspace",
        back_populates="conversations",
    )

    customer = relationship(
        "Customer",
        back_populates="conversations",
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )

    __table_args__ = (
        Index(
            "ix_conversations_workspace_id_status",
            "workspace_id",
            "status",
        ),
    )
