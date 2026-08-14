"""Phase 4: unique constraint on workflow_tasks (workflow_id, node_id).

Duplicate step rows (from repeated test runs) caused MultipleResultsFound in
the dispatch engine. The unique constraint prevents duplicates going forward;
existing duplicates are pruned keeping the earliest-created row per node.
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prune any existing duplicate step rows (keep the earliest per node).
    op.execute(
        """
        DELETE FROM workflow_tasks
        WHERE id::text NOT IN (
            SELECT min(id::text)
            FROM workflow_tasks
            GROUP BY workflow_id, node_id
        )
        """
    )
    op.create_unique_constraint(
        "uq_workflow_task_node", "workflow_tasks", ["workflow_id", "node_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_workflow_task_node", "workflow_tasks", type_="unique")
