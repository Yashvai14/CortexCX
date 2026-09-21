from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Coupon(BaseModel):
    __tablename__ = "coupons"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    discount_type: Mapped[str] = mapped_column(
        String(20),
        default="percentage",
        nullable=False,
    )

    discount_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    min_order_amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max_uses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    uses_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workspace = relationship("Workspace")

    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_coupons_workspace_code"),
        Index("ix_coupons_workspace_active", "workspace_id", "is_active"),
    )
