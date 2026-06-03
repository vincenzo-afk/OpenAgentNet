from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowTask


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrchestrationService:
    async def create_workflow(
        self,
        db: AsyncSession,
        owner_agent_id: str,
        definition: dict[str, Any],
        name: str,
    ) -> dict[str, Any]:
        workflow = Workflow(
            owner_agent_id=uuid.UUID(owner_agent_id),
            name=name,
            status="pending",
            definition=definition,
            context={},
        )
        db.add(workflow)
        await db.flush()

        # Create workflow tasks from definition
        for task_def in definition.get("tasks", []):
            workflow_task = WorkflowTask(
                workflow_id=workflow.id,
                node_id=task_def["id"],
                capability_name=task_def["agent_capability"],
                depends_on=task_def.get("depends_on", []),
                status="pending",
            )
            db.add(workflow_task)

        await db.flush()
        return self._workflow_to_dict(workflow)

    async def get_workflow(self, db: AsyncSession, workflow_id: str) -> dict[str, Any] | None:
        result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
        workflow = result.scalar_one_or_none()
        if not workflow:
            return None

        # Load workflow tasks
        tasks_result = await db.execute(
            select(WorkflowTask).where(WorkflowTask.workflow_id == workflow.id)
        )
        tasks = tasks_result.scalars().all()

        return self._workflow_to_dict(workflow, tasks)

    async def list_workflows(
        self,
        db: AsyncSession,
        agent_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(Workflow).where(Workflow.owner_agent_id == uuid.UUID(agent_id))
        count_query = select(func.count(Workflow.id)).where(
            Workflow.owner_agent_id == uuid.UUID(agent_id)
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Workflow.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        workflows = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._workflow_to_dict(w) for w in workflows],
        }

    def _workflow_to_dict(
        self, workflow: Workflow, tasks: list[WorkflowTask] | None = None
    ) -> dict[str, Any]:
        task_list = []
        if tasks:
            task_list = [
                {
                    "id": str(t.id),
                    "node_id": t.node_id,
                    "capability_name": t.capability_name,
                    "depends_on": t.depends_on,
                    "status": t.status,
                    "result": t.result,
                }
                for t in tasks
            ]

        return {
            "workflow_id": str(workflow.id),
            "name": workflow.name,
            "status": workflow.status,
            "definition": workflow.definition,
            "context": workflow.context,
            "result": workflow.result,
            "error": workflow.error,
            "tasks": task_list,
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
        }
