"""Add dispute review queue fields and workflow/trust event infrastructure.

- disputes.reviewed_at, verified_flag (penalty multiplier)
- Note: trust_records and endorsements already have the columns needed for
  weighted endorsement scoring; no table changes required for them.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disputes",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "disputes",
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=True,
            comment="True when resolved_valid, False when resolved_invalid, None when open",
        ),
    )


def downgrade() -> None:
    op.drop_column("disputes", "verified")
    op.drop_column("disputes", "reviewed_at")
