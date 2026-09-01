"""add ai support fields

Revision ID: 1c842f60bf6e
Revises: 9f9f1e258309
Create Date: 2026-09-01 16:17:52.900431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c842f60bf6e'
down_revision: Union[str, Sequence[str], None] = '9f9f1e258309'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add AI value to messagesendertype enum in PostgreSQL
    op.execute("ALTER TYPE messagesendertype ADD VALUE IF NOT EXISTS 'AI'")

    # 2. Add ai_enabled and ai_state columns to conversations table
    op.add_column(
        'conversations',
        sa.Column('ai_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False)
    )
    op.add_column(
        'conversations',
        sa.Column('ai_state', sa.String(length=50), server_default=sa.text("'idle'"), nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('conversations', 'ai_state')
    op.drop_column('conversations', 'ai_enabled')
