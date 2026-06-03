from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, Numeric, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrustRecord(Base):
    __tablename__ = "trust_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    trust_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.500)
    outcome_rate: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.500)
    endorsement_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.500)
    age_factor: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.100)
    dispute_penalty: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.000)
    total_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispute_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("idx_trust_score", "trust_score"),
        Index("idx_trust_agent", "agent_id"),
    )


class Endorsement(Base):
    __tablename__ = "endorsements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint("from_agent_id != to_agent_id", name="no_self_endorse"),
        Index("idx_endorsements_to", "to_agent_id"),
        Index("idx_endorsements_from", "from_agent_id"),
    )


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reported_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporter_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint("reported_agent_id != reporter_agent_id", name="no_self_report"),
        CheckConstraint(
            "status IN ('open', 'under_review', 'resolved_valid', 'resolved_invalid', 'withdrawn')",
            name="check_dispute_status",
        ),
    )
