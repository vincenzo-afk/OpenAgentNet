from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.config import get_settings
from app.models.task import Task
from app.models.trust import Dispute, Endorsement, TrustRecord


def utcnow() -> datetime:
    return datetime.now(UTC)


class TrustService:
    def _compute_trust_score(self, record: TrustRecord) -> float:
        settings = get_settings()
        score = (
            settings.trust_weight_outcome * float(record.outcome_rate)
            + settings.trust_weight_latency * 0.8  # placeholder for latency adherence
            + settings.trust_weight_dispute * (1.0 - float(record.dispute_penalty))
            + settings.trust_weight_age * float(record.age_factor)
        )
        return round(min(max(score, 0.0), 1.0), 3)

    async def get_trust_record(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        result = await db.execute(
            select(TrustRecord).where(TrustRecord.agent_id == uuid.UUID(agent_id))
        )
        record = result.scalar_one_or_none()
        if not record:
            # Create initial record
            record = TrustRecord(agent_id=uuid.UUID(agent_id))
            db.add(record)
            await db.flush()
            return self._record_to_dict(record)
        return self._record_to_dict(record)

    async def record_outcome(
        self,
        db: AsyncSession,
        task_id: str,
        success: bool,
        execution_ms: int | None = None,
    ) -> None:
        task_result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
        task = task_result.scalar_one_or_none()
        if not task:
            return

        # Update trust record for executor
        agent_id = task.to_agent_id
        result = await db.execute(select(TrustRecord).where(TrustRecord.agent_id == agent_id))
        record = result.scalar_one_or_none()
        if not record:
            record = TrustRecord(agent_id=agent_id)
            db.add(record)

        record.total_tasks += 1
        if success:
            record.successful_tasks += 1
        record.outcome_rate = (
            record.successful_tasks / record.total_tasks if record.total_tasks > 0 else 0.5
        )
        record.trust_score = self._compute_trust_score(record)
        record.last_computed_at = utcnow()
        record.updated_at = utcnow()

    async def endorse(
        self,
        db: AsyncSession,
        from_agent_id: str,
        to_agent_id: str,
        capability: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        if from_agent_id == to_agent_id:
            raise ValueError("Cannot self-endorse")

        # Get endorser's trust score for weight
        endorser_result = await db.execute(
            select(TrustRecord).where(TrustRecord.agent_id == uuid.UUID(from_agent_id))
        )
        endorser_trust = endorser_result.scalar_one_or_none()
        endorser_score = float(endorser_trust.trust_score) if endorser_trust else 0.5
        # SECURITY.md: endorsement weight from agents with trust_score < 0.3 should be zero
        weight = endorser_score if endorser_score >= 0.3 else 0.0

        # Check for existing endorsement
        existing = await db.execute(
            select(Endorsement).where(
                Endorsement.from_agent_id == uuid.UUID(from_agent_id),
                Endorsement.to_agent_id == uuid.UUID(to_agent_id),
                Endorsement.capability == capability,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Endorsement already exists for this capability")

        endorsement = Endorsement(
            from_agent_id=uuid.UUID(from_agent_id),
            to_agent_id=uuid.UUID(to_agent_id),
            capability=capability,
            comment=comment,
            weight=weight,
        )
        db.add(endorsement)
        await db.flush()

        # Update endorsement score
        target_result = await db.execute(
            select(TrustRecord).where(TrustRecord.agent_id == uuid.UUID(to_agent_id))
        )
        target_record = target_result.scalar_one_or_none()
        if target_record:
            # Recompute endorsement score
            avg_result = await db.execute(
                select(func.avg(Endorsement.weight)).where(
                    Endorsement.to_agent_id == uuid.UUID(to_agent_id)
                )
            )
            avg_weight = avg_result.scalar() or 0.5
            target_record.endorsement_score = float(avg_weight)
            target_record.trust_score = self._compute_trust_score(target_record)
            target_record.updated_at = utcnow()

        return {
            "id": str(endorsement.id),
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "capability": capability,
            "comment": comment,
            "weight": weight,
            "created_at": endorsement.created_at.isoformat() if endorsement.created_at else None,
        }

    async def flag(
        self,
        db: AsyncSession,
        reported_agent_id: str,
        reporter_agent_id: str,
        reason: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if reported_agent_id == reporter_agent_id:
            raise ValueError("Cannot report yourself")

        dispute = Dispute(
            reported_agent_id=uuid.UUID(reported_agent_id),
            reporter_agent_id=uuid.UUID(reporter_agent_id),
            task_id=uuid.UUID(task_id) if task_id else None,
            reason=reason,
            status="open",
        )
        db.add(dispute)
        await db.flush()

        # Audit log: trust flag submitted (SECURITY.md requirement)
        await log_audit_event(
            db,
            event_type="trust_flag_submitted",
            actor_id=uuid.UUID(reporter_agent_id),
            target_id=uuid.UUID(reported_agent_id),
            target_type="agent",
            payload={"reason": reason, "task_id": task_id},
        )

        return {
            "id": str(dispute.id),
            "reported_agent_id": reported_agent_id,
            "reporter_agent_id": reporter_agent_id,
            "reason": reason,
            "status": "open",
            "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        }

    async def get_events(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        events = []

        # Get trust record history
        result = await db.execute(
            select(TrustRecord).where(TrustRecord.agent_id == uuid.UUID(agent_id))
        )
        record = result.scalar_one_or_none()
        if not record:
            return []

        # Add initial event
        events.append(
            {
                "event_id": str(record.id),
                "event_type": "trust_initialized",
                "score_delta": 0.5,
                "new_score": float(record.trust_score),
                "reference_id": None,
                "timestamp": record.created_at.isoformat() if record.created_at else None,
            }
        )

        # Add endorsement events
        endorsements_result = await db.execute(
            select(Endorsement).where(Endorsement.to_agent_id == uuid.UUID(agent_id)).limit(limit)
        )
        for endorsement in endorsements_result.scalars().all():
            events.append(
                {
                    "event_id": str(endorsement.id),
                    "event_type": "endorsement_received",
                    "score_delta": float(endorsement.weight) * 0.05,
                    "new_score": float(record.trust_score),
                    "reference_id": str(endorsement.from_agent_id),
                    "timestamp": endorsement.created_at.isoformat()
                    if endorsement.created_at
                    else None,
                }
            )

        # Add dispute events
        disputes_result = await db.execute(
            select(Dispute).where(Dispute.reported_agent_id == uuid.UUID(agent_id)).limit(limit)
        )
        for dispute in disputes_result.scalars().all():
            events.append(
                {
                    "event_id": str(dispute.id),
                    "event_type": "dispute_filed",
                    "score_delta": -0.1,
                    "new_score": float(record.trust_score),
                    "reference_id": str(dispute.reporter_agent_id),
                    "timestamp": dispute.created_at.isoformat() if dispute.created_at else None,
                }
            )

        return sorted(events, key=lambda x: x.get("timestamp") or "", reverse=True)[:limit]

    def _record_to_dict(self, record: TrustRecord) -> dict[str, Any]:
        return {
            "agent_id": str(record.agent_id),
            "score": float(record.trust_score),
            "components": {
                "task_completion_rate": float(record.outcome_rate),
                "latency_adherence": float(record.endorsement_score),
                "dispute_outcome": 1.0 - float(record.dispute_penalty),
                "age_factor": float(record.age_factor),
            },
            "total_tasks": record.total_tasks,
            "successful_tasks": record.successful_tasks,
            "dispute_count": record.dispute_count,
            "last_active": record.last_computed_at.isoformat() if record.last_computed_at else None,
            "computed_at": record.last_computed_at.isoformat() if record.last_computed_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
