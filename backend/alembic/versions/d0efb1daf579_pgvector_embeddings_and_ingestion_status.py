"""pgvector embeddings and ingestion status

Revision ID: d0efb1daf579
Revises: 4522cfe07132
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings

revision: str = "d0efb1daf579"
down_revision: Union[str, None] = "4522cfe07132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dim = int(settings.EMBEDDING_DIMENSION)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Old array(float) embeddings came from the random mock embedder (and a different dimension),
    # so they are not carried over: documents are re-embedded with the real model (see /knowledge/reindex).
    op.drop_column("document_chunks", "embedding")
    op.execute(f"ALTER TABLE document_chunks ADD COLUMN embedding vector({dim})")
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=100), nullable=True))
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "error_message")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
    op.add_column(
        "document_chunks",
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )
