"""Add team-scoped memory permissions.

Revision ID: 020
Revises: 019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("memory_permissions", "grantee_agent_id", nullable=True)
    op.add_column(
        "memory_permissions",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_memory_permissions_team_id",
        "memory_permissions",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "unique_memory_team_permission", "memory_permissions", ["memory_id", "team_id"]
    )
    op.create_check_constraint(
        "check_memory_permission_target",
        "memory_permissions",
        "(grantee_agent_id IS NOT NULL AND team_id IS NULL) OR "
        "(grantee_agent_id IS NULL AND team_id IS NOT NULL)",
    )
    op.create_index("idx_memory_permissions_team", "memory_permissions", ["team_id"])


def downgrade() -> None:
    op.drop_index("idx_memory_permissions_team", table_name="memory_permissions")
    op.drop_constraint("check_memory_permission_target", "memory_permissions", type_="check")
    op.drop_constraint("unique_memory_team_permission", "memory_permissions", type_="unique")
    op.drop_constraint("fk_memory_permissions_team_id", "memory_permissions", type_="foreignkey")
    op.drop_column("memory_permissions", "team_id")
    op.alter_column("memory_permissions", "grantee_agent_id", nullable=False)
