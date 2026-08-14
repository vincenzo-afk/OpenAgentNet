"""Add negotiation history (counter-proposals) and negotiation event audit.

Phase 3: Negotiation state machine.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "negotiation_rounds",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("negotiation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text, nullable=False),  # requester | target
        sa.Column("decision", sa.Text, nullable=False),  # proposed | accepted | countered | declined
        sa.Column("proposal", JSONB, nullable=False, default=dict),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('requester', 'target')", name="check_neg_round_role"
        ),
        sa.CheckConstraint(
            "decision IN ('proposed', 'accepted', 'countered', 'declined')",
            name="check_neg_round_decision",
        ),
    )
    op.create_index("idx_neg_rounds_negotiation", "negotiation_rounds", ["negotiation_id"])


def downgrade() -> None:
    op.drop_index("idx_neg_rounds_negotiation", table_name="negotiation_rounds")
    op.drop_table("negotiation_rounds")
