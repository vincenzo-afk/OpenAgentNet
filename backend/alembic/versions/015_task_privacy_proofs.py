"""Add privacy-preserving task proofs.

Revision ID: 015
Revises: 014
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_privacy_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme", sa.Text(), nullable=False),
        sa.Column("commitment", sa.Text(), nullable=False),
        sa.Column("proof", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_privacy_proofs_task"),
    )
    op.create_index("idx_task_privacy_proofs_created", "task_privacy_proofs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_task_privacy_proofs_created", table_name="task_privacy_proofs")
    op.drop_table("task_privacy_proofs")
