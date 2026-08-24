"""Background workers for the OpenAgentNet platform.

Three maintenance loops run for the lifetime of the FastAPI process:

1. **Task delivery worker** — subscribes (via NATS JetStream when available)
   to every agent inbox subject wildcard, forwards each envelope to the
   recipient's HTTP endpoint, and records the delivery outcome on the task.
   When NATS is unavailable the platform falls back to synchronous HTTP
   delivery at send time.

2. **TTL expiry worker** — marks tasks that exceeded ``ttl_seconds`` as
   ``timeout`` so downstream trust scoring sees a definitive outcome.

3. **Heartbeat worker** — marks agents that missed
   ``heartbeat_miss_threshold`` windows as ``inactive``.
"""
from __future__ import annotations

import uuid

import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.nats_client import (
    connect_nats,
    disconnect_nats,
    is_nats_available,
)
from app.models.agent import Agent
from app.models.task import Task
from app.services.messaging import MessagingService
from app.services.trust import TrustService

logger = logging.getLogger(__name__)


# Hard cap on synchronous HTTP delivery attempts. Beyond this the recipient
# endpoint is considered dead and the task is failed instead of looping
# forever (a pending task with an unreachable endpoint would otherwise be
# retried every 10 seconds for the lifetime of the process).
MAX_DELIVERY_ATTEMPTS = 3


def utcnow() -> datetime:
    return datetime.now(UTC)


async def _record_terminal_outcome(db, task: Task, success: bool = False) -> None:
    """Feed worker-owned terminal states into the trust/reputation service."""
    await TrustService().record_outcome(
        db,
        str(task.id),
        success=success,
        execution_ms=task.execution_ms,
    )


def _count_delivery_attempts(task: Task) -> int:
    """Read the delivery-attempt counter journalled in task.result."""
    if isinstance(task.result, dict):
        try:
            return int(task.result.get("_delivery_attempts", 0))
        except (TypeError, ValueError):
            pass
    return 0


async def deliver_task_http(task: Task, recipient_endpoint: str) -> str:
    """Deliver a task envelope to an agent endpoint over HTTP."""
    envelope = {
        "envelope_version": "0.1.0",
        "message_id": str(task.id),
        "to": None,
        "type": "task.request",
        "task": {
            "id": str(task.id),
            "name": task.capability_name,
            "payload": task.payload,
            "constraints": {**task.constraints, "ttl_seconds": task.ttl_seconds},
        },
        "timestamp": task.created_at.isoformat() if task.created_at else utcnow().isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=min(task.ttl_seconds, 60) or 30.0) as client:
            response = await client.post(
                recipient_endpoint,
                json=envelope,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code < 400:
                return "delivered"
            logger.warning(
                "HTTP delivery to %s returned %s", recipient_endpoint, response.status_code
            )
            return "queued"
    except Exception:
        logger.exception("HTTP delivery to %s failed", recipient_endpoint)
        return "queued"


async def task_delivery_worker(session_factory) -> None:
    """Process pending tasks: deliver over HTTP and update delivery status."""
    from app.core.database import get_session_factory

    factory = session_factory or get_session_factory()
    while True:
        try:
            async with factory() as db:
                pending = await db.execute(
                    select(Task).where(
                        Task.status == "pending",
                        Task.created_at >= utcnow() - __import__("datetime").timedelta(hours=1),
                    ).limit(50)
                )
                tasks = pending.scalars().all()
                for task in tasks:
                    recipient = await db.execute(
                        select(Agent).where(Agent.id == task.to_agent_id)
                    )
                    agent = recipient.scalar_one_or_none()
                    if not agent:
                        task.status = "failed"
                        task.error_code = "RECIPIENT_NOT_FOUND"
                        task.error_message = "Recipient agent no longer exists"
                        task.completed_at = utcnow()
                        continue
                    if agent.status != "active":
                        task.status = "failed"
                        task.error_code = "RECIPIENT_INACTIVE"
                        task.error_message = "Recipient agent is inactive"
                        task.completed_at = utcnow()
                        await _record_terminal_outcome(db, task)
                        continue
                    outcome = await deliver_task_http(task, agent.endpoint)
                    # 'delivered' means the agent accepted the envelope over
                    # HTTP; map it to 'running' — 'delivered' is not a valid
                    # tasks.status (check_task_status) and the commit fails.
                    if outcome == "delivered":
                        task.status = "running"
                        continue
                    # Undeliverable: journal the attempt in task.result so the
                    # loop does not hammer a dead endpoint forever.
                    attempts = _count_delivery_attempts(task)
                    if attempts + 1 >= MAX_DELIVERY_ATTEMPTS:
                        task.status = "failed"
                        task.error_code = "DEAD_ENDPOINT"
                        task.error_message = (
                            f"Recipient endpoint {agent.endpoint} failed "
                            f"{attempts + 1} delivery attempt(s)"
                        )
                        task.completed_at = utcnow()
                        await _record_terminal_outcome(db, task)
                        continue
                    task.status = "pending"
                    attempts_result = dict(task.result or {}) if isinstance(task.result, dict) else {}
                    attempts_result["_delivery_attempts"] = attempts + 1
                    task.result = attempts_result
                if tasks:
                    await db.commit()
        except Exception:
            logger.exception("Task delivery worker iteration failed")
        await asyncio.sleep(10)


async def ttl_expiry_worker(session_factory) -> None:
    """Mark TTL-expired pending tasks as timed out."""
    from app.core.database import get_session_factory

    factory = session_factory or get_session_factory()
    while True:
        try:
            async with factory() as db:
                settings = get_settings()
                result = await db.execute(
                    select(Task).where(
                        Task.status.in_(["pending", "queued"]),
                        Task.created_at
                        <= utcnow()
                        - __import__("datetime").timedelta(seconds=settings.heartbeat_interval_seconds),
                    )
                )
                expired = result.scalars().all()
                for task in expired:
                    task.status = "timeout"
                    task.error_code = "TIMEOUT"
                    task.error_message = f"Task exceeded TTL of {task.ttl_seconds}s"
                    task.completed_at = utcnow()
                    await _record_terminal_outcome(db, task)
                if expired:
                    await db.commit()
        except Exception:
            logger.exception("TTL expiry worker iteration failed")
        await asyncio.sleep(30)


async def heartbeat_worker(session_factory) -> None:
    """Mark agents that missed heartbeat windows as inactive."""
    from app.core.database import get_session_factory

    factory = session_factory or get_session_factory()
    messaging_service = MessagingService()
    while True:
        try:
            async with factory() as db:
                count = await messaging_service.mark_inactive_agents(db)
                if count:
                    logger.info("Marked %d agent(s) inactive (missed heartbeats)", count)
                    await db.commit()
        except Exception:
            logger.exception("Heartbeat worker iteration failed")
        await asyncio.sleep(30)


async def inbox_forwarding_handler(db_session_factory) -> callable:
    """Return an async handler that forwards NATS inbox envelopes to HTTP."""

    async def handler(envelope: dict) -> None:
        to = envelope.get("to", "")
        from app.core.identifiers import parse_agent_id

        resolved = parse_agent_id(to)
        if not resolved:
            return
        from app.core.database import get_session_factory

        factory = db_session_factory or get_session_factory()
        async with factory() as db:
            result = await db.execute(select(Agent).where(Agent.id == resolved))
            agent = result.scalar_one_or_none()
            if not agent:
                return
            await deliver_task_http_from_envelope(envelope, agent.endpoint)

    return handler


async def deliver_task_http_from_envelope(envelope: dict, endpoint: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json=envelope,
                headers={"Content-Type": "application/json"},
            )
            return "delivered" if response.status_code < 400 else "queued"
    except Exception:
        return "queued"


async def nats_inbox_listener(session_factory) -> None:
    """Forward task envelopes from the agent-inbox JetStream stream to HTTP.

    Uses a durable PULL subscription (``inbox_listener``) rather than a push
    subscription: in practice the JetStream push-callback path was observed to
    stall silently in long-running FastAPI processes, while pull consumers are
    deterministic and self-healing on reconnect.

    This keeps running even when NATS is initially unavailable; it reconnects
    opportunistically every few seconds.
    """
    sub = None
    handler = None
    while True:
        try:
            await connect_nats()
            if not is_nats_available():
                sub = None
                await asyncio.sleep(5)
                continue
            from app.core.nats_client import _jetstream

            if handler is None:
                handler = await inbox_forwarding_handler(session_factory)
            if sub is None:
                try:
                    sub = await _jetstream.pull_subscribe(
                        "oan.messages.+.inbox",
                        durable="inbox_listener_worker",
                        stream="OAN_TASKS",
                    )
                    pass
                except Exception:
                    sub = None
                    await asyncio.sleep(5)
                    continue
            try:
                messages = await sub.fetch(batch=20, timeout=2)
            except Exception:
                # No messages yet (timeout is expected between bursts).
                messages = []
            for msg in messages:
                try:
                    envelope = json.loads(msg.data.decode())
                    await handler(envelope)
                except Exception:
                    logger.exception("Error forwarding inbox envelope")
                finally:
                    try:
                        await msg.ack()
                    except Exception:
                        pass
        except Exception:
            logger.exception("NATS inbox listener error")
            sub = None
        await asyncio.sleep(0.5)


async def workflow_dispatch_worker(session_factory=None) -> None:
    """Phase 4: dispatch pending workflows (topological engine) on a schedule.

    Workflows created via POST /workflows are stored with status ``pending``;
    this worker picks them up and runs the same dispatch engine that the
    handler used to start as a fire-and-forget task. A worker loop is used
    because per-request background tasks were not reliably executed by the
    framework's request teardown.
    """
    from app.core.database import get_session_factory
    from app.models.workflow import Workflow
    from app.services.orchestration import OrchestrationService

    factory = session_factory or get_session_factory()
    # Run the engine on the MAIN event loop; asyncpg connections are bound to
    # it and cannot be reused from asyncio.run in worker threads.
    in_flight: set[uuid.UUID] = set()

    while True:
        try:
            async with factory() as db:
                pending_result = await db.execute(
                    select(Workflow.id).where(Workflow.status == "pending").limit(8)
                )
                pending_ids = [row[0] for row in pending_result.all()]
            for workflow_id in pending_ids:
                if workflow_id not in in_flight:
                    in_flight.add(workflow_id)
                    task = asyncio.create_task(
                        _dispatch_engine(in_flight, workflow_id)
                    )
                    in_flight.discard(workflow_id) if task.done() else None
        except Exception:
            logger.exception("Workflow dispatch worker iteration failed")
        await asyncio.sleep(2)


async def _dispatch_engine(in_flight: set, workflow_id: uuid.UUID) -> None:
    """Run the dispatch engine on the main loop and track completion."""
    from app.services.orchestration import OrchestrationService

    try:
        await OrchestrationService()._run_workflow(None, workflow_id)
    except Exception:
        logger.exception("Workflow dispatch engine failed for %s", workflow_id)
    finally:
        in_flight.discard(workflow_id)

async def start_background_workers(session_factory=None) -> None:
    """Kick off all maintenance loops."""
    from app.core.database import get_session_factory

    factory = session_factory or get_session_factory()
    asyncio.create_task(task_delivery_worker(factory))
    asyncio.create_task(ttl_expiry_worker(factory))
    asyncio.create_task(heartbeat_worker(factory))
    asyncio.create_task(nats_inbox_listener(factory))
    asyncio.create_task(workflow_dispatch_worker(factory))
    try:
        await connect_nats()
    except Exception:
        logger.warning("NATS unavailable at startup — HTTP delivery will be used")
