from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.task import Task
from app.core.crypto import base64_to_public_key, verify_signature, canonical_json_bytes
from app.core.audit import log_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessagingService:
    async def send_message(
        self, db: AsyncSession, envelope: dict[str, Any], sender_id: str
    ) -> dict[str, Any]:
        # Check message deduplication (FR-MSG-005)
        message_id = envelope.get("message_id")
        if message_id:
            existing = await db.execute(select(Task).where(Task.id == uuid.UUID(message_id)))
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
        capability = task_data.get("name", "") if isinstance(task_data, dict) else ""

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
        result = await db.execute(select(Task).where(Task.id == uuid.UUID(message_id)))
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
        return {
            "message_id": str(task.id),
            "from_agent_id": str(task.from_agent_id),
            "to_agent_id": str(task.to_agent_id),
            "type": "task.request",
            "payload": task.payload,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "delivered_at": task.completed_at.isoformat() if task.completed_at else None,
        }
