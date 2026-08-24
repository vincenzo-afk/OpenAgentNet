"""Add accepted negotiation task contracts.

Revision ID: 019
Revises: 018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("negotiation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("session_token", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'consumed', 'cancelled')",
            name="check_task_contract_status",
        ),
        sa.ForeignKeyConstraint(["negotiation_id"], ["negotiations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("negotiation_id"),
    )
    op.create_index("idx_task_contracts_requester", "task_contracts", ["requester_id"])
    op.create_index("idx_task_contracts_target", "task_contracts", ["target_id"])
    op.create_index("idx_task_contracts_status", "task_contracts", ["status"])
    op.add_column(
        "tasks",
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "contract_id")
    op.drop_index("idx_task_contracts_status", table_name="task_contracts")
    op.drop_index("idx_task_contracts_target", table_name="task_contracts")
    op.drop_index("idx_task_contracts_requester", table_name="task_contracts")
    op.drop_table("task_contracts")
