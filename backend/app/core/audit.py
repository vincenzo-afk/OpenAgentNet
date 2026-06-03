from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


async def log_audit_event(
    db: AsyncSession,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    target_type: str | None = None,
    payload: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Log an audit event to the audit_events table."""
    audit = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        target_id=target_id,
        target_type=target_type,
        payload=payload or {},
        ip_address=ip_address,
    )
    db.add(audit)
    await db.flush()
