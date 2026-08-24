"""Add provider-agnostic marketplace escrow ledger.

Revision ID: 017
Revises: 016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketplace_escrows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("status", sa.Text(), nullable=False, server_default="held"),
        sa.Column("provider_reference", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "amount > 0",
            name="check_marketplace_escrow_amount_positive",
        ),
        sa.CheckConstraint(
            "status IN ('held', 'released', 'refunded', 'disputed')",
            name="check_marketplace_escrow_status",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["buyer_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_marketplace_escrows_task_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_marketplace_escrows_idempotency_key"),
    )
    op.create_index("idx_marketplace_escrows_listing", "marketplace_escrows", ["listing_id"])
    op.create_index("idx_marketplace_escrows_buyer", "marketplace_escrows", ["buyer_agent_id"])
    op.create_index("idx_marketplace_escrows_seller", "marketplace_escrows", ["seller_agent_id"])
    op.create_index("idx_marketplace_escrows_status", "marketplace_escrows", ["status"])


def downgrade() -> None:
    op.drop_index("idx_marketplace_escrows_status", table_name="marketplace_escrows")
    op.drop_index("idx_marketplace_escrows_seller", table_name="marketplace_escrows")
    op.drop_index("idx_marketplace_escrows_buyer", table_name="marketplace_escrows")
    op.drop_index("idx_marketplace_escrows_listing", table_name="marketplace_escrows")
    op.drop_table("marketplace_escrows")
