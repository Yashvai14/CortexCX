from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class ChannelIdentity(BaseModel):
    __tablename__ = "channel_identities"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    channel_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    workspace = relationship("Workspace")
    customer = relationship("Customer")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "channel_type",
            "channel_user_id",
            name="uq_channel_identities_workspace_type_user",
        ),
    )
