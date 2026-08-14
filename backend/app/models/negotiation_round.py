from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class NegotiationRound(Base):
    """One step of a negotiation: the original proposal, counters, and the final decision."""

    __tablename__ = "negotiation_rounds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    negotiation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # requester | target
    decision: Mapped[str] = mapped_column(Text, nullable=False)  # proposed | accepted | countered | declined
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "role IN ('requester', 'target')", name="check_neg_round_role"
        ),
        CheckConstraint(
            "decision IN ('proposed', 'accepted', 'countered', 'declined')",
            name="check_neg_round_decision",
        ),
    )
