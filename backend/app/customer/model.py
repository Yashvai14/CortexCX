from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Customer(BaseModel):
    __tablename__ = "customers"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    status: Mapped[CustomerStatus] = mapped_column(
        SQLEnum(CustomerStatus, name="customerstatus"),
        default=CustomerStatus.ACTIVE,
        nullable=False,
    )

    workspace = relationship(
        "Workspace",
        back_populates="customers",
    )

    conversations = relationship(
        "Conversation",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "email",
            name="uq_customers_workspace_email",
        ),
        Index(
            "ix_customers_workspace_id_email",
            "workspace_id",
            "email",
        ),
    )
