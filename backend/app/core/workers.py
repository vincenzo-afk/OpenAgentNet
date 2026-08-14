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
    subscribe_agent_inbox,
)
from app.models.agent import Agent
from app.models.task import Task
from app.services.messaging import MessagingService

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


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
                    outcome = await deliver_task_http(task, agent.endpoint)
                    task.status = outcome if outcome == "delivered" else "pending"
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
    """Subscribe to the agent-inbox wildcard and forward envelopes to HTTP.

    This keeps running even when NATS is initially unavailable; it reconnects
    opportunistically every 15 seconds.
    """
    while True:
        try:
            await connect_nats()
            if is_nats_available():
                await subscribe_agent_inbox(
                    "+",
                    await inbox_forwarding_handler(session_factory),
                    wildcard=True,
                )
        except Exception:
            logger.exception("NATS inbox listener error")
        await asyncio.sleep(15)


async def start_background_workers(session_factory=None) -> None:
    """Kick off all maintenance loops."""
    from app.core.database import get_session_factory

    factory = session_factory or get_session_factory()
    asyncio.create_task(task_delivery_worker(factory))
    asyncio.create_task(ttl_expiry_worker(factory))
    asyncio.create_task(heartbeat_worker(factory))
    asyncio.create_task(nats_inbox_listener(factory))
    try:
        await connect_nats()
    except Exception:
        logger.warning("NATS unavailable at startup — HTTP delivery will be used")
