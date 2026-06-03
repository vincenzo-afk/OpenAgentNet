from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(INET)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("idx_audit_events_type", "event_type"),
        Index("idx_audit_events_actor", "actor_id"),
        Index("idx_audit_events_target", "target_id"),
        Index("idx_audit_events_time", "occurred_at"),
    )
