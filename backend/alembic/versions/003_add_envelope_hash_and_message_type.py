"""Add envelope_hash dedup column and message type to tasks

Revision ID: 003
Revises: 002
Create Date: 2026-08-14 08:40:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("envelope_hash", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("type", sa.Text(), nullable=False, server_default="task.request"))
    op.create_index(
        "idx_tasks_envelope_hash",
        "tasks",
        ["envelope_hash"],
        postgresql_where=sa.text("envelope_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_envelope_hash", table_name="tasks")
    op.drop_column("tasks", "type")
    op.drop_column("tasks", "envelope_hash")
