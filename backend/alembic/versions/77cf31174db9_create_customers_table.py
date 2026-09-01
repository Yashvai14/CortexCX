"""create customers table

Revision ID: 77cf31174db9
Revises: d2107e530732
Create Date: 2026-09-01 15:46:11.385370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77cf31174db9'
down_revision: Union[str, Sequence[str], None] = 'd2107e530732'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'customers',
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('company_name', sa.String(length=150), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', name='customerstatus'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'email', name='uq_customers_workspace_email')
    )
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=False)
    op.create_index(op.f('ix_customers_workspace_id'), 'customers', ['workspace_id'], unique=False)
    op.create_index('ix_customers_workspace_id_email', 'customers', ['workspace_id', 'email'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_customers_workspace_id_email', table_name='customers')
    op.drop_index(op.f('ix_customers_workspace_id'), table_name='customers')
    op.drop_index(op.f('ix_customers_email'), table_name='customers')
    op.drop_table('customers')
    op.execute('DROP TYPE IF EXISTS customerstatus')
