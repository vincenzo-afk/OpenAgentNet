from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.crypto import base64_to_public_key, canonical_json_bytes, verify_signature
from app.models.agent import Agent
from app.models.task import Task


def utcnow() -> datetime:
    return datetime.now(UTC)


class MessagingService:
    async def send_heartbeat(self, db: AsyncSession, agent_id: str) -> dict[str, Any]:
        """Record a heartbeat from an agent (PROTOCOL.md section 10)."""
        try:
            agent_uuid = uuid.UUID(agent_id)
        except (ValueError, AttributeError):
            raise ValueError("Invalid agent_id")
        result = await db.execute(
            select(Agent).where(Agent.id == agent_uuid, Agent.deleted_at.is_(None))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")
        agent.last_seen_at = utcnow()
        agent.updated_at = utcnow()
        await db.flush()
        return {
            "agent_id": agent_id,
            "status": "ok",
            "last_seen_at": agent.last_seen_at.isoformat(),
        }

    async def mark_inactive_agents(self, db: AsyncSession) -> int:
        """Mark agents as inactive if they missed heartbeats (PROTOCOL.md section 10)."""
        from app.core.config import get_settings

        settings = get_settings()
        threshold = utcnow() - __import__("datetime").timedelta(
            seconds=settings.heartbeat_interval_seconds * settings.heartbeat_miss_threshold
        )
        result = await db.execute(
            select(Agent).where(
                Agent.status == "active",
                Agent.deleted_at.is_(None),
                Agent.last_seen_at < threshold,
            )
        )
        agents = result.scalars().all()
        for agent in agents:
            agent.status = "inactive"
            agent.updated_at = utcnow()
        if agents:
            await db.flush()
        return len(agents)

    async def send_message(
        self, db: AsyncSession, envelope: dict[str, Any], sender_id: str
    ) -> dict[str, Any]:
        # Check message deduplication (FR-MSG-005)
        message_id = envelope.get("message_id")
        if message_id:
            try:
                msg_uuid = uuid.UUID(message_id)
            except (ValueError, AttributeError):
                msg_uuid = None
            if msg_uuid:
                existing = await db.execute(select(Task).where(Task.id == msg_uuid))
                if existing.scalar_one_or_none():
                    raise ValueError("Duplicate message_id")

        # Check TTL enforcement (FR-MSG-006)
        ttl_seconds = envelope.get("ttl_seconds", 60)
        if ttl_seconds <= 0:
            raise ValueError("Message TTL has expired")

        # Resolve recipient
        recipient_did = envelope.get("to", "")
        recipient_result = await db.execute(
            select(Agent).where(
                Agent.did == recipient_did,
                Agent.deleted_at.is_(None),
                Agent.status == "active",
            )
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient:
            raise ValueError("Recipient not found or inactive")

        # Verify sender
        sender_result = await db.execute(
            select(Agent).where(
                Agent.id == uuid.UUID(sender_id),
                Agent.deleted_at.is_(None),
            )
        )
        sender = sender_result.scalar_one_or_none()
        if not sender:
            raise ValueError("Sender not found")

        # Verify signature if provided (FR-MSG-004)
        signature = envelope.get("signature")
        if signature:
            body = {k: v for k, v in envelope.items() if k != "signature"}
            canonical = canonical_json_bytes(body)
            public_key = base64_to_public_key(sender.public_key)
            if not verify_signature(public_key, signature, canonical):
                raise ValueError("Invalid message signature")

        if not message_id:
            message_id = str(uuid.uuid4())

        task_data = envelope.get("task") or envelope.get("body") or envelope.get("payload") or {}
        if isinstance(task_data, str):
            capability = task_data
            task_data = {"name": task_data}
        elif isinstance(task_data, dict):
            capability = task_data.get("name", task_data.get("slug", ""))
        else:
            capability = ""
            task_data = {}

        # Create task record
        task = Task(
            id=uuid.UUID(message_id),
            from_agent_id=sender.id,
            to_agent_id=recipient.id,
            capability_name=capability,
            payload=task_data,
            constraints=envelope.get("constraints", {}),
            status="pending",
            ttl_seconds=ttl_seconds,
        )
        db.add(task)
        await db.flush()

        # Audit log: message sent (SECURITY.md requirement)
        await log_audit_event(
            db,
            event_type="message_sent",
            actor_id=sender.id,
            target_id=recipient.id,
            target_type="agent",
            payload={"message_id": message_id, "capability": capability},
        )

        # Try HTTP delivery
        delivery_mode = "http"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    recipient.endpoint,
                    json=envelope,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code >= 400:
                    delivery_mode = "queued"
        except Exception:
            delivery_mode = "queued"

        return {
            "message_id": message_id,
            "status": "queued",
            "delivery_mode": delivery_mode,
        }

    async def get_message(
        self, db: AsyncSession, message_id: str, agent_id: str
    ) -> dict[str, Any] | None:
        try:
            msg_uuid = uuid.UUID(message_id)
        except (ValueError, AttributeError):
            return None
        result = await db.execute(select(Task).where(Task.id == msg_uuid))
        task = result.scalar_one_or_none()
        if not task:
            return None

        # Check access
        agent_uuid = uuid.UUID(agent_id)
        if task.from_agent_id != agent_uuid and task.to_agent_id != agent_uuid:
            return None

        return self._task_to_dict(task)

    async def list_messages(
        self,
        db: AsyncSession,
        agent_id: str,
        direction: str | None = None,
        message_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        agent_uuid = uuid.UUID(agent_id)
        query = select(Task)

        if direction == "sent":
            query = query.where(Task.from_agent_id == agent_uuid)
        elif direction == "received":
            query = query.where(Task.to_agent_id == agent_uuid)
        else:
            query = query.where(
                (Task.from_agent_id == agent_uuid) | (Task.to_agent_id == agent_uuid)
            )

        # Apply time filters
        if since:
            query = query.where(Task.created_at >= since)
        if until:
            query = query.where(Task.created_at <= until)

        count_query = select(func.count(Task.id))
        if direction == "sent":
            count_query = count_query.where(Task.from_agent_id == agent_uuid)
        elif direction == "received":
            count_query = count_query.where(Task.to_agent_id == agent_uuid)
        else:
            count_query = count_query.where(
                (Task.from_agent_id == agent_uuid) | (Task.to_agent_id == agent_uuid)
            )

        if since:
            count_query = count_query.where(Task.created_at >= since)
        if until:
            count_query = count_query.where(Task.created_at <= until)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        tasks = result.scalars().all()

        items = [self._task_to_dict(t) for t in tasks]
        # Filter by message_type if provided
        if message_type:
            items = [i for i in items if i["type"] == message_type]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    def _task_to_dict(self, task: Task) -> dict[str, Any]:
        capability = ""
        if isinstance(task.payload, dict):
            capability = task.payload.get("name", task.payload.get("slug", ""))
        return {
            "message_id": str(task.id),
            "from_agent_id": str(task.from_agent_id),
            "to_agent_id": str(task.to_agent_id),
            "capability": capability,
            "type": "task.request",
            "payload": task.payload,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "delivered_at": task.completed_at.isoformat() if task.completed_at else None,
        }
