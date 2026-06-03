"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY, INET

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agents table
    op.create_table(
        "agents",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("did", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("health_endpoint", sa.Text),
        sa.Column("public_key", sa.Text, nullable=False),
        sa.Column("key_id", sa.Text, nullable=False),
        sa.Column("protocol_version", sa.Text, nullable=False, server_default="0.1.0"),
        sa.Column("capabilities", JSONB, nullable=False, server_default="[]"),
        sa.Column("permissions_required", JSONB, nullable=False, server_default="[]"),
        sa.Column("permissions_offered", JSONB, nullable=False, server_default="[]"),
        sa.Column("tags", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_agents_status", "agents", ["status"], postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index("idx_agents_tags", "agents", ["tags"], postgresql_using="gin")
    op.create_index("idx_agents_capabilities", "agents", ["capabilities"], postgresql_using="gin")
    op.create_index("idx_agents_owner", "agents", ["owner_id"])

    # api_keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.Text, unique=True, nullable=False),
        sa.Column("key_prefix", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_api_keys_agent", "api_keys", ["agent_id"])

    # trust_records table
    op.create_table(
        "trust_records",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("agent_id", UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("trust_score", sa.Numeric(4, 3), nullable=False, server_default="0.500"),
        sa.Column("outcome_rate", sa.Numeric(4, 3), nullable=False, server_default="0.500"),
        sa.Column("endorsement_score", sa.Numeric(4, 3), nullable=False, server_default="0.500"),
        sa.Column("age_factor", sa.Numeric(4, 3), nullable=False, server_default="0.100"),
        sa.Column("dispute_penalty", sa.Numeric(4, 3), nullable=False, server_default="0.000"),
        sa.Column("total_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("successful_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("dispute_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_trust_score", "trust_records", ["trust_score"])
    op.create_index("idx_trust_agent", "trust_records", ["agent_id"])

    # endorsements table
    op.create_table(
        "endorsements",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("from_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("to_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Text, nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("weight", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_endorsements_to", "endorsements", ["to_agent_id"])
    op.create_index("idx_endorsements_from", "endorsements", ["from_agent_id"])

    # disputes table
    op.create_table(
        "disputes",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("reported_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True)),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("evidence", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.Text),
        sa.Column("resolved_by", UUID(as_uuid=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # negotiations table
    op.create_table(
        "negotiations",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("requester_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="proposed"),
        sa.Column("proposal", JSONB, nullable=False),
        sa.Column("response", JSONB),
        sa.Column("session_token", sa.Text, unique=True),
        sa.Column("round_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # tasks table
    op.create_table(
        "tasks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("from_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("to_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True)),
        sa.Column("workflow_id", UUID(as_uuid=True)),
        sa.Column("capability_name", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("constraints", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("result", JSONB),
        sa.Column("error_code", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("negotiation_id", UUID(as_uuid=True)),
        sa.Column("execution_ms", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("ttl_seconds", sa.Integer, nullable=False, server_default="60"),
    )
    op.create_index("idx_tasks_from_agent", "tasks", ["from_agent_id"])
    op.create_index("idx_tasks_to_agent", "tasks", ["to_agent_id"])
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_created_at", "tasks", ["created_at"])

    # workflows table
    op.create_table(
        "workflows",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("owner_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("context", JSONB, nullable=False, server_default="{}"),
        sa.Column("result", JSONB),
        sa.Column("error", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # workflow_tasks table
    op.create_table(
        "workflow_tasks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("workflow_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True)),
        sa.Column("node_id", sa.Text, nullable=False),
        sa.Column("capability_name", sa.Text, nullable=False),
        sa.Column("depends_on", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("result", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_workflow_tasks_workflow", "workflow_tasks", ["workflow_id"])

    # memory_objects table
    op.create_table(
        "memory_objects",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("namespace", sa.Text, nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("owner_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("data_type", sa.Text, nullable=False, server_default="json"),
        sa.Column("is_ephemeral", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("owner_agent_id", "namespace", "key", name="unique_memory_key"),
    )
    op.create_index("idx_memory_namespace", "memory_objects", ["owner_agent_id", "namespace"])

    # memory_permissions table
    op.create_table(
        "memory_permissions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("memory_id", UUID(as_uuid=True), nullable=False),
        sa.Column("grantee_agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.Text, nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("memory_id", "grantee_agent_id", name="unique_memory_permission"),
    )

    # marketplace_listings table
    op.create_table(
        "marketplace_listings",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("agent_id", UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("long_description", sa.Text),
        sa.Column("pricing", JSONB, nullable=False, server_default="{}"),
        sa.Column("sla", JSONB, nullable=False, server_default="{}"),
        sa.Column("tiers", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("target_id", UUID(as_uuid=True)),
        sa.Column("target_type", sa.Text),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", INET),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_audit_events_type", "audit_events", ["event_type"])
    op.create_index("idx_audit_events_actor", "audit_events", ["actor_id"])
    op.create_index("idx_audit_events_target", "audit_events", ["target_id"])
    op.create_index("idx_audit_events_time", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("marketplace_listings")
    op.drop_table("memory_permissions")
    op.drop_table("memory_objects")
    op.drop_table("workflow_tasks")
    op.drop_table("workflows")
    op.drop_table("tasks")
    op.drop_table("negotiations")
    op.drop_table("disputes")
    op.drop_table("endorsements")
    op.drop_table("trust_records")
    op.drop_table("api_keys")
    op.drop_table("agents")
