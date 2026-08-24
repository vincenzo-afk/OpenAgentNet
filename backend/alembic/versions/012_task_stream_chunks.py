"""Add incremental task stream chunks.

Revision ID: 012
Revises: 011
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_stream_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("chunk", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "sequence", name="uq_task_stream_chunk_sequence"),
    )
    op.create_index(
        "idx_task_stream_chunks_task_sequence",
        "task_stream_chunks",
        ["task_id", "sequence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_task_stream_chunks_task_sequence", table_name="task_stream_chunks")
    op.drop_table("task_stream_chunks")
