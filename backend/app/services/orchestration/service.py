from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.models.workflow import Workflow, WorkflowTask

MAX_RETRIES = 2
MAX_STEP_RUN_TIME_SECONDS = 30


def utcnow() -> datetime:
    return datetime.now(UTC)


def validate_dag(tasks: list[dict[str, Any]]) -> str | None:
    """Validate workflow definition as a DAG.

    Returns an error string describing the problem, or None when valid.
    Detects duplicate node ids, dangling dependencies, and cycles.
    """
    ids: set[str] = set()
    adjacency: dict[str, list[str]] = defaultdict(list)
    for task_def in tasks:
        node_id = task_def.get("id", "")
        if not node_id:
            return "Step is missing an id"
        if node_id in ids:
            return f"Duplicate step id: {node_id}"
        ids.add(node_id)
        for dep in task_def.get("depends_on", []):
            adjacency[dep].append(node_id)

    # dependency referenced by a task but not defined as a step
    for task_def in tasks:
        for dep in task_def.get("depends_on", []):
            if dep not in ids:
                return f"Step '{task_def.get('id')}' depends on undefined step '{dep}'"

    # Cycle detection via Kahn's algorithm
    in_degree = {nid: 0 for nid in ids}
    for task_def in tasks:
        for dep in task_def.get("depends_on", []):
            if dep in ids:
                in_degree[task_def["id"]] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in adjacency.get(node, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if visited != len(ids):
        return "Workflow contains a cycle"
    return None


def topological_order(tasks: list[dict[str, Any]]) -> list[str]:
    """Return node ids in execution order (dependencies first)."""
    ids: set[str] = set()
    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {}
    for task_def in tasks:
        node_id = task_def["id"]
        ids.add(node_id)
        in_degree[node_id] = len(task_def.get("depends_on", []))
        for dep in task_def.get("depends_on", []):
            adjacency[dep].append(node_id)

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in adjacency.get(node, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return order


async def _emit_workflow_event(event_type: str, workflow: Workflow, extra: dict[str, Any] | None = None) -> None:
    try:
        from app.core import nats_client

        await nats_client.publish_event(
            "workflow",
            {
                "type": event_type,
                "workflow_id": str(workflow.id),
                "owner_agent_id": str(workflow.owner_agent_id),
                "name": workflow.name,
                "status": workflow.status,
                **(extra or {}),
            },
        )
    except Exception:
        pass


class OrchestrationService:
    async def create_workflow(
        self,
        db: AsyncSession,
        owner_agent_id: str,
        definition: dict[str, Any],
        name: str,
    ) -> dict[str, Any]:
        owner_uuid = parse_agent_id(owner_agent_id)
        if not owner_uuid:
            raise ValueError("Invalid agent id")

        tasks_def = definition.get("tasks", [])
        if not tasks_def:
            raise ValueError("Workflow must define at least one step")

        error = validate_dag(tasks_def)
        if error:
            raise ValueError(error)

        # Owner cannot be the sole participant in a real network, but a
        # workflow is allowed to include the owner as a step host when
        # discovery finds no one else — the engine resolves hosts lazily.
        workflow = Workflow(
            owner_agent_id=owner_uuid,
            name=name,
            status="pending",
            definition=definition,
            context=definition.get("context", {}),
        )
        db.add(workflow)
        await db.flush()

        for task_def in tasks_def:
            workflow_task = WorkflowTask(
                workflow_id=workflow.id,
                node_id=task_def["id"],
                capability_name=task_def["agent_capability"],
                depends_on=task_def.get("depends_on", []),
                status="pending",
                result=None,
            )
            db.add(workflow_task)

        # Commit the workflow + steps before dispatching so that the
        # background dispatch worker, which opens its own session, can see
        # the newly created row (transaction isolation).
        await db.commit()
        # Phase 4: dispatch is handled by the workflow_dispatch_worker
        # background loop (see app.core.workers), which picks up pending
        # workflows within seconds of creation.
        await _emit_workflow_event("workflow_created", workflow)

        return self._workflow_to_dict(workflow)

    async def get_workflow(self, db: AsyncSession, workflow_id: str) -> dict[str, Any] | None:
        result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
        workflow = result.scalar_one_or_none()
        if not workflow:
            return None

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
        owner = parse_agent_id(agent_id)
        query = select(Workflow).where(Workflow.owner_agent_id == owner)
        count_query = select(func.count(Workflow.id)).where(Workflow.owner_agent_id == owner)

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

    async def _run_workflow(self, db: AsyncSession, workflow_id: uuid.UUID) -> None:
        """Phase 4 dispatch engine: topological execution with retry and partial results."""
        from app.core.database import get_session_factory

        logger.info("Workflow dispatch starting for %s", workflow_id)
        try:
            session_factory = get_session_factory()

            async with session_factory() as session:
                # Claim the workflow atomically (FOR UPDATE): concurrent
                # worker iterations or retried dispatches skip workflows
                # already claimed by another engine run.
                workflow_result = await session.execute(
                    select(Workflow)
                    .where(Workflow.id == workflow_id)
                    .with_for_update()
                )
                workflow = workflow_result.scalar_one_or_none()
                if not workflow or workflow.status != "pending":
                    logger.info(
                        "Dispatch aborted for workflow %s: found=%s status=%s",
                        workflow_id,
                        workflow is not None,
                        getattr(workflow, "status", None),
                    )
                    return

                workflow.status = "running"
                workflow.updated_at = utcnow()
                await session.flush()
                await _emit_workflow_event("workflow_started", workflow)

                order = topological_order(workflow.definition.get("tasks", []))
                node_map = {t["id"]: t for t in workflow.definition.get("tasks", [])}

                failed_steps: list[dict[str, str]] = []

                for node_id in order:
                    task_result = await session.execute(
                        select(WorkflowTask).where(
                            WorkflowTask.workflow_id == workflow_id,
                            WorkflowTask.node_id == node_id,
                        )
                    )
                    step = task_result.scalar_one_or_none()
                    if not step or step.status in ("success", "partial", "failed"):
                        continue

                    # Skip steps whose dependencies failed (cascade)
                    deps_ok = True
                    for dep in step.depends_on:
                        if not await self._dep_successful(session, workflow_id, dep):
                            deps_ok = False
                            break
                    if not deps_ok:
                        step.status = "failed"
                        step.result = {"skipped": True, "reason": "dependency_failed"}
                        failed_steps.append({"node_id": node_id, "reason": "dependency_failed"})
                        await session.flush()
                        await _emit_workflow_event(
                            "workflow_step_failed", workflow, {"node_id": node_id, "reason": "dependency_failed"}
                        )
                        continue

                    attempt = 0
                    outcome: dict[str, Any] | None = None
                    while attempt <= MAX_RETRIES:
                        # Each (re)delivery gets a fresh message id so the
                        # envelope-hash dedup does not reject retries.
                        node_def = dict(node_map[node_id])
                        node_def["_attempt_message_id"] = str(uuid.uuid4())
                        try:
                            outcome = await self._execute_step(
                                session,
                                workflow,
                                node_def,
                                step,
                            )
                            break
                        except Exception as exc:  # noqa: BLE001
                            attempt += 1
                            if attempt > MAX_RETRIES:
                                outcome = {"error": str(exc), "retries_exhausted": True}
                            else:
                                await asyncio.sleep(1)

                    if outcome and outcome.get("error"):
                        step.status = "failed"
                        step.result = outcome
                        failed_steps.append({"node_id": node_id, "error": outcome.get("error", "")})
                        await _emit_workflow_event(
                            "workflow_step_failed", workflow, {"node_id": node_id, "error": outcome.get("error", "")}
                        )
                    elif outcome and outcome.get("partial"):
                        step.status = "partial"
                        step.result = outcome
                        await _emit_workflow_event(
                            "workflow_step_partial", workflow, {"node_id": node_id}
                        )
                    else:
                        step.status = "success"
                        step.result = outcome
                        await _emit_workflow_event(
                            "workflow_step_completed", workflow, {"node_id": node_id}
                        )
                    await session.flush()

                # Aggregate workflow result
                workflow.updated_at = utcnow()
                workflow.completed_at = utcnow()
                if failed_steps and len(failed_steps) < len(order):
                    workflow.status = "partial"
                    workflow.result = {"completed": len(order) - len(failed_steps), "failed": failed_steps}
                    await _emit_workflow_event("workflow_partial", workflow, {"failed_steps": failed_steps})
                elif failed_steps:
                    workflow.status = "failed"
                    workflow.error = {"failed_steps": failed_steps}
                    await _emit_workflow_event("workflow_failed", workflow, {"failed_steps": failed_steps})
                else:
                    workflow.status = "success"
                    workflow.result = {"completed": len(order)}
                    await _emit_workflow_event("workflow_completed", workflow)

                await session.commit()
        except Exception:
            logger.exception("Workflow dispatch engine failed for %s", workflow_id)
            try:
                from app.core.database import get_session_factory as _gsf

                async with _gsf()() as _s:
                    _w = (await _s.execute(select(Workflow).where(Workflow.id == workflow_id))).scalar_one_or_none()
                    if _w and _w.status == "running":
                        _w.status = "failed"
                        _w.error = {"engine_error": "dispatch_task_failed"}
                        _w.completed_at = utcnow()
                        _w.updated_at = utcnow()
                        await _s.commit()
                        await _emit_workflow_event("workflow_failed", _w, {"engine_error": "dispatch_task_failed"})
            except Exception:
                logger.exception("Failed to mark workflow %s as failed after engine error", workflow_id)
        else:
            logger.info("Dispatch task completed for workflow %s", workflow_id)

    async def _dep_successful(self, session: AsyncSession, workflow_id: uuid.UUID, dep_node_id: str) -> bool:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.workflow_id == workflow_id,
                WorkflowTask.node_id == dep_node_id,
            )
        )
        dep = result.scalar_one_or_none()
        return dep is not None and dep.status in ("success", "partial")

    async def _execute_step(
        self,
        db: AsyncSession,
        workflow: Workflow,
        node_def: dict[str, Any],
        step: WorkflowTask,
    ) -> dict[str, Any] | None:
        """Resolve a host agent for the step capability and dispatch the task."""
        from app.models.agent import Agent
        from app.services.messaging import MessagingService

        # Resolve an active agent offering the capability.
        # Capabilities are stored as a JSONB list of {name, ...} objects, so
        # match on JSONB containment.
        result = await db.execute(
            select(Agent.id)
            .where(
                Agent.capabilities.contains([{"name": node_def["agent_capability"]}]),
                Agent.status == "active",
            )
            .order_by(Agent.last_seen_at.desc().nullslast(), Agent.updated_at.desc())
        )
        hosts = [str(a) for a in result.scalars().all()]
        # Prefer a host that is not the workflow owner (dispatch to the network)
        if len(hosts) > 1:
            owner = str(workflow.owner_agent_id)
            others = [h for h in hosts if h != owner]
            if others:
                hosts = others
        if not hosts:
            raise RuntimeError(
                f"No active agent found for capability {node_def['agent_capability']}"
            )
        host_id = hosts[0]

        payload = dict(node_def.get("payload") or {})
        payload["workflow_context"] = workflow.context or {}
        payload["workflow_node"] = node_def["id"]
        if node_def.get("_attempt_message_id"):
            payload["_attempt_message_id"] = node_def["_attempt_message_id"]

        logger.info("Executing workflow step %s", node_def["id"])
        messaging = MessagingService()
        envelope = {
            "to": f"did:oan:{host_id}",
            "task": node_def["agent_capability"],
            "payload": payload,
            "constraints": node_def.get("constraints", {}),
            "ttl_seconds": 60,
            "message_id": node_def.get("_attempt_message_id"),
        }
        # owner_agent cannot be the sender identity here; pass workflow owner
        send_result = await messaging.send_message(db, envelope, str(workflow.owner_agent_id))
        task_id = send_result["message_id"]

        # Mark step as executing
        step.task_id = uuid.UUID(task_id) if task_id else step.task_id
        await db.flush()

        # Poll for the dispatched task result. The task row must be fetched
        # fresh on every iteration and all attributes read immediately, before
        # the next db.execute — asyncpg closes the previous CursorResult when a
        # new query runs, and accessing attributes of a stale ORM object then
        # raises "This result object is closed."
        deadline = datetime.now(UTC).timestamp() + MAX_STEP_RUN_TIME_SECONDS
        while datetime.now(UTC).timestamp() < deadline:
            await asyncio.sleep(1)
            result = await db.execute(
                select(TaskModel).where(TaskModel.id == uuid.UUID(task_id))
            )
            task = result.scalar_one_or_none()
            if task is None:
                continue
            # Capture terminal attributes eagerly while the CursorResult is open
            t_status = task.status
            t_result = task.result if isinstance(task.result, dict) else {}
            t_error = task.error_message
            if t_status in ("success", "partial", "failed", "declined", "timeout", "cancelled"):
                if t_status == "success":
                    return t_result
                if t_status == "partial":
                    return {"partial": True, **t_result}
                raise RuntimeError(
                    t_result.get("error_message")
                    or t_error
                    or f"Step execution ended with status {task.status}"
                )
        raise RuntimeError("Step execution timed out")

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


TaskModel = None  # patched after import to avoid circular dependency at module load


def _patch_task_model() -> None:
    from app.models.task import Task

    global TaskModel
    TaskModel = Task


_patch_task_model()
