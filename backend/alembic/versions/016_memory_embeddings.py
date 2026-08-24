"""Add pgvector embeddings for semantic memory search.

Revision ID: 016
Revises: 015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "memory_objects",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "idx_memory_embedding_hnsw",
        "memory_objects",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_memory_embedding_hnsw", table_name="memory_objects")
    op.drop_column("memory_objects", "embedding")
