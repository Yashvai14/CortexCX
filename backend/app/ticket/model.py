from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Ticket(BaseModel):
    __tablename__ = "tickets"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Human-friendly sequential number, unique per workspace (shown as TCK-1001)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)

    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(TicketStatus, name="ticketstatus"),
        default=TicketStatus.OPEN,
        nullable=False,
        index=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(TicketPriority, name="ticketpriority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer")
    conversation = relationship("Conversation")
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    comments = relationship(
        "TicketComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketComment.created_at",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "number", name="uq_tickets_workspace_number"),
        Index("ix_tickets_workspace_status", "workspace_id", "status"),
    )


class TicketComment(BaseModel):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal notes are visible to staff only; non-internal are customer-facing replies
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # System events (status changes, assignment) are rendered as timeline entries
    is_event: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User")
