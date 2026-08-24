"""Add region and federation provenance to agents.

Revision ID: 010
Revises: 83b3f3c6072b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "83b3f3c6072b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("region", sa.Text(), nullable=False, server_default="local"),
    )
    op.add_column(
        "agents",
        sa.Column("is_federated", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column("agents", sa.Column("origin_registry_id", sa.Text(), nullable=True))
    op.create_index("idx_agents_region_status", "agents", ["region", "status"], unique=False)
    op.create_index("idx_agents_federated_origin", "agents", ["origin_registry_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_agents_federated_origin", table_name="agents")
    op.drop_index("idx_agents_region_status", table_name="agents")
    op.drop_column("agents", "origin_registry_id")
    op.drop_column("agents", "is_federated")
    op.drop_column("agents", "region")
