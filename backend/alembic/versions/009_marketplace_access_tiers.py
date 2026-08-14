"""marketplace access tiers and usage metering

Revision ID: 009
Revises: 008
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision = "009"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_listings",
        sa.Column("access_tier", sa.Text(), nullable=False, server_default="free"),
    )
    op.add_column(
        "marketplace_listings",
        sa.Column("tier_details", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "marketplace_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("marketplace_usage")
    op.drop_column("marketplace_listings", "tier_details")
    op.drop_column("marketplace_listings", "access_tier")
