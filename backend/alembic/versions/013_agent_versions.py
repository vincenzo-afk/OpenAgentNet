"""Add agent version history.

Revision ID: 013
Revises: 012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "revision", name="uq_agent_versions_revision"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO agent_versions
                (id, agent_id, revision, version, endpoint, capabilities, metadata, created_at)
            SELECT gen_random_uuid(), id, 1, version, endpoint, capabilities, metadata, created_at
            FROM agents
            WHERE deleted_at IS NULL
            """
        )
    )
    op.create_index(
        "idx_agent_versions_agent_created",
        "agent_versions",
        ["agent_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_agent_versions_agent_created", table_name="agent_versions")
    op.drop_table("agent_versions")
