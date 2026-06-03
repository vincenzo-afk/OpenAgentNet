"""Add missing check constraints and indexes

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agents table - check constraints
    op.create_check_constraint(
        "check_agent_status",
        "agents",
        "status IN ('active', 'inactive', 'suspended', 'deregistered')",
    )
    op.create_check_constraint(
        "check_owner_type",
        "agents",
        "owner_type IN ('user', 'organization')",
    )

    # api_keys table - FK constraint and index
    op.create_foreign_key(
        "fk_api_keys_agent_id",
        "api_keys",
        "agents",
        ["agent_id"],
        ["id"],
    )
    op.create_index(
        "idx_api_keys_hash", "api_keys", ["key_hash"], postgresql_where=sa.text("is_active = TRUE")
    )

    # trust_records table - FK, check constraint and DESC index
    op.create_foreign_key(
        "fk_trust_records_agent_id",
        "trust_records",
        "agents",
        ["agent_id"],
        ["id"],
    )
    op.create_check_constraint(
        "check_trust_score_range",
        "trust_records",
        "trust_score >= 0.0 AND trust_score <= 1.0",
    )
    op.drop_index("idx_trust_score", "trust_records")
    op.create_index("idx_trust_score", "trust_records", [sa.text("trust_score DESC")])

    # endorsements table - FK, unique constraint
    op.create_foreign_key(
        "fk_endorsements_from_agent",
        "endorsements",
        "agents",
        ["from_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_endorsements_to_agent",
        "endorsements",
        "agents",
        ["to_agent_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "unique_endorsement",
        "endorsements",
        ["from_agent_id", "to_agent_id", "capability"],
    )
    op.create_check_constraint(
        "no_self_endorse",
        "endorsements",
        "from_agent_id != to_agent_id",
    )

    # disputes table - FK, check constraints
    op.create_foreign_key(
        "fk_disputes_reported_agent",
        "disputes",
        "agents",
        ["reported_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_disputes_reporter_agent",
        "disputes",
        "agents",
        ["reporter_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_disputes_task_id",
        "disputes",
        "tasks",
        ["task_id"],
        ["id"],
    )
    op.create_check_constraint(
        "no_self_report",
        "disputes",
        "reported_agent_id != reporter_agent_id",
    )
    op.create_check_constraint(
        "check_dispute_status",
        "disputes",
        "status IN ('open', 'under_review', 'resolved_valid', 'resolved_invalid', 'withdrawn')",
    )

    # negotiations table - FK, check constraint
    op.create_foreign_key(
        "fk_negotiations_requester",
        "negotiations",
        "agents",
        ["requester_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_negotiations_target",
        "negotiations",
        "agents",
        ["target_id"],
        ["id"],
    )
    op.create_check_constraint(
        "check_negotiation_status",
        "negotiations",
        "status IN ('proposed', 'countered', 'accepted', 'declined', 'expired')",
    )

    # tasks table - FK, check constraint
    op.create_foreign_key(
        "fk_tasks_from_agent",
        "tasks",
        "agents",
        ["from_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tasks_to_agent",
        "tasks",
        "agents",
        ["to_agent_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tasks_workflow_id",
        "tasks",
        "workflows",
        ["workflow_id"],
        ["id"],
    )
    op.create_check_constraint(
        "check_task_status",
        "tasks",
        "status IN ('pending', 'acked', 'running', 'success', 'partial', 'failed', 'declined', 'cancelled', 'timeout')",
    )
    op.create_index(
        "idx_tasks_workflow",
        "tasks",
        ["workflow_id"],
        postgresql_where=sa.text("workflow_id IS NOT NULL"),
    )

    # workflows table - check constraint
    op.create_check_constraint(
        "check_workflow_status",
        "workflows",
        "status IN ('pending', 'running', 'success', 'partial', 'failed', 'cancelled')",
    )

    # workflow_tasks table - FK
    op.create_foreign_key(
        "fk_workflow_tasks_workflow",
        "workflow_tasks",
        "workflows",
        ["workflow_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_workflow_tasks_task",
        "workflow_tasks",
        "tasks",
        ["task_id"],
        ["id"],
    )

    # marketplace_listings table - FK
    op.create_foreign_key(
        "fk_marketplace_listings_agent",
        "marketplace_listings",
        "agents",
        ["agent_id"],
        ["id"],
    )

    # memory_permissions table - FK with cascade and check constraint
    op.create_foreign_key(
        "fk_memory_permissions_memory_id",
        "memory_permissions",
        "memory_objects",
        ["memory_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "check_memory_permission",
        "memory_permissions",
        "permission IN ('read', 'read_write')",
    )

    # audit_events table - DESC index
    op.drop_index("idx_audit_events_time", "audit_events")
    op.create_index("idx_audit_events_time", "audit_events", [sa.text("occurred_at DESC")])


def downgrade() -> None:
    # Revert index changes
    op.drop_index("idx_audit_events_time", "audit_events")
    op.create_index("idx_audit_events_time", "audit_events", ["occurred_at"])

    op.drop_constraint("check_memory_permission", "memory_permissions", type_="check")
    op.drop_constraint("fk_memory_permissions_memory_id", "memory_permissions", type_="foreignkey")

    op.drop_constraint("fk_marketplace_listings_agent", "marketplace_listings", type_="foreignkey")

    op.drop_constraint("fk_workflow_tasks_task", "workflow_tasks", type_="foreignkey")
    op.drop_constraint("fk_workflow_tasks_workflow", "workflow_tasks", type_="foreignkey")

    op.drop_constraint("check_workflow_status", "workflows", type_="check")
    op.drop_constraint("fk_tasks_workflow_id", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_to_agent", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_from_agent", "tasks", type_="foreignkey")
    op.drop_constraint("check_task_status", "tasks", type_="check")
    op.drop_index("idx_tasks_workflow", "tasks")

    op.drop_constraint("check_negotiation_status", "negotiations", type_="check")
    op.drop_constraint("fk_negotiations_target", "negotiations", type_="foreignkey")
    op.drop_constraint("fk_negotiations_requester", "negotiations", type_="foreignkey")

    op.drop_constraint("check_dispute_status", "disputes", type_="check")
    op.drop_constraint("no_self_report", "disputes", type_="check")
    op.drop_constraint("fk_disputes_task_id", "disputes", type_="foreignkey")
    op.drop_constraint("fk_disputes_reporter_agent", "disputes", type_="foreignkey")
    op.drop_constraint("fk_disputes_reported_agent", "disputes", type_="foreignkey")

    op.drop_constraint("no_self_endorse", "endorsements", type_="check")
    op.drop_constraint("unique_endorsement", "endorsements", type_="unique")
    op.drop_constraint("fk_endorsements_to_agent", "endorsements", type_="foreignkey")
    op.drop_constraint("fk_endorsements_from_agent", "endorsements", type_="foreignkey")

    op.drop_index("idx_trust_score", "trust_records")
    op.create_index("idx_trust_score", "trust_records", ["trust_score"])
    op.drop_constraint("check_trust_score_range", "trust_records", type_="check")
    op.drop_constraint("fk_trust_records_agent_id", "trust_records", type_="foreignkey")

    op.drop_index("idx_api_keys_hash", "api_keys")
    op.drop_constraint("fk_api_keys_agent_id", "api_keys", type_="foreignkey")
    op.drop_constraint("check_owner_type", "agents", type_="check")
    op.drop_constraint("check_agent_status", "agents", type_="check")
