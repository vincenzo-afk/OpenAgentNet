"""Trust & Reputation service (Phase 2 — Trust and Reputation, v0.2.0).

Composite trust score components (see docs/DESIGN.md and SECURITY.md):

- outcome_rate     : successful tasks / total tasks (weighted by settings)
- latency_adherence: placeholder (0.8 fixed baseline until latency targets land)
- endorsement_score: weighted mean of endorsement weights; each endorser's
  weight is its own trust_score dampened (transitive trust with decay).
  Endorsement rings (A→B→A) count at most one direction.
- age_factor       : log growth with agent age in days, capped at 1.0
- dispute_penalty  : verified disputes subtract from the score, unverified
  (open) disputes are excluded so reporters cannot weaponize flags

Anomaly detection emits `anomaly_detected` trust events for:
- sudden success-rate spikes after long dormancy
- endorsement rings (mutual endorsements with no task history)
- endorsement bursts (>=3 endorsements within 5 minutes)
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.config import get_settings
from app.core.identifiers import parse_agent_id
from app.models.task import Task
from app.models.trust import Dispute, Endorsement, TrustRecord

BURST_WINDOW_MINUTES = 5
BURST_THRESHOLD = 3


def utcnow() -> datetime:
    return datetime.now(UTC)


class TrustService:
    async def _get_record(self, db: AsyncSession, agent_id: uuid.UUID | str) -> TrustRecord | None:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Invalid agent_id")
        result = await db.execute(select(TrustRecord).where(TrustRecord.agent_id == resolved))
        return result.scalar_one_or_none()

    def _score_age(self, record: TrustRecord) -> float:
        if not record.created_at:
            return 0.1
        age_days = (utcnow() - record.created_at).total_seconds() / 86400.0
        if age_days <= 0:
            return 0.1
        factor = min(1.0, 0.2 + 0.08 * (age_days ** 0.5))
        return round(factor, 3)

    def _compute_trust_score(self, record: TrustRecord) -> float:
        settings = get_settings()
        age_factor = self._score_age(record)
        record.age_factor = age_factor
        score = (
            settings.trust_weight_outcome * float(record.outcome_rate)
            + settings.trust_weight_latency * 0.8  # placeholder for latency adherence
            + settings.trust_weight_dispute * (1.0 - float(record.dispute_penalty))
            + settings.trust_weight_age * age_factor
        )
        return round(min(max(score, 0.0), 1.0), 3)

    async def get_trust_record(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Invalid agent_id")
        result = await db.execute(select(TrustRecord).where(TrustRecord.agent_id == resolved))
        record = result.scalar_one_or_none()
        if not record:
            # Create initial record
            record = TrustRecord(agent_id=resolved)
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

        agent_id = task.to_agent_id
        record = await self._get_record(db, agent_id)
        if not record:
            record = TrustRecord(agent_id=agent_id)
            db.add(record)

        record.total_tasks += 1
        if success:
            record.successful_tasks += 1
        record.outcome_rate = (
            record.successful_tasks / record.total_tasks if record.total_tasks > 0 else 0.5
        )
        await self._check_anomalies(db, record)
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

        from_uuid = parse_agent_id(from_agent_id)
        to_uuid = parse_agent_id(to_agent_id)
        if not from_uuid or not to_uuid:
            raise ValueError("Invalid agent id")

        # Ensure the endorsed agent has a trust record so endorsement events and
        # anomaly timelines are visible before any task outcome occurs.
        target_record = await self._get_record(db, to_uuid)
        if not target_record:
            target_record = TrustRecord(agent_id=to_uuid)
            db.add(target_record)
            await db.flush()

        # Endorser's trust score weights the endorsement (transitive trust).
        endorser = await self._get_record(db, from_uuid)
        endorser_score = float(endorser.trust_score) if endorser else 0.5
        weight = endorser_score if endorser_score >= 0.3 else 0.0

        existing = await db.execute(
            select(Endorsement).where(
                Endorsement.from_agent_id == from_uuid,
                Endorsement.to_agent_id == to_uuid,
                Endorsement.capability == capability,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Endorsement already exists for this capability")

        endorsement = Endorsement(
            from_agent_id=from_uuid,
            to_agent_id=to_uuid,
            capability=capability,
            comment=comment,
            weight=weight,
        )
        db.add(endorsement)
        await db.flush()

        # Ring check: if the target also endorsed the source, flag the anomaly.
        if await self._endorsement_ring_exists(db, from_uuid, to_uuid):
            await self._emit_anomaly(
                db, to_uuid, "endorsement_ring",
                {"from_agent_id": from_agent_id, "to_agent_id": to_agent_id, "capability": capability},
            )

        # Burst check: endorsements received in the last BURST_WINDOW_MINUTES.
        burst = await db.execute(
            select(func.count(Endorsement.id)).where(
                Endorsement.to_agent_id == to_uuid,
                Endorsement.created_at >= utcnow() - timedelta(minutes=BURST_WINDOW_MINUTES),
            )
        )
        burst_count = burst.scalar()
        if burst_count is not None and burst_count >= BURST_THRESHOLD:
            await self._emit_anomaly(
                db, to_uuid, "endorsement_burst", {"window_minutes": BURST_WINDOW_MINUTES},
            )

        await self._recompute_endorsement_score(db, to_uuid)
        return {
            "id": str(endorsement.id),
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "capability": capability,
            "comment": comment,
            "weight": weight,
            "created_at": endorsement.created_at.isoformat() if endorsement.created_at else None,
        }

    async def _endorsement_ring_exists(
        self, db: AsyncSession, a: uuid.UUID, b: uuid.UUID
    ) -> bool:
        row = await db.execute(
            select(Endorsement.id).where(
                Endorsement.from_agent_id == b, Endorsement.to_agent_id == a,
            ).limit(1)
        )
        return row.scalar_one_or_none() is not None

    async def _recompute_endorsement_score(self, db: AsyncSession, target: uuid.UUID) -> None:
        """Mean of endorsement weights, with ring-aware dampening.

        For each mutual endorsement pair only the first-created direction
        contributes; all one-direction endorsements always contribute.
        """
        rows = await db.execute(
            select(
                Endorsement.weight, Endorsement.id,
                Endorsement.from_agent_id, Endorsement.to_agent_id,
                Endorsement.created_at,
            ).where(Endorsement.to_agent_id == target).order_by(Endorsement.created_at)
        )
        all_rows = rows.all()
        if not all_rows:
            target_record = await self._get_record(db, target)
            if target_record:
                target_record.endorsement_score = 0.5
                target_record.trust_score = self._compute_trust_score(target_record)
            return

        weights: list[float] = []
        counted_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for w, eid, frm, to, _created in all_rows:
            reverse_pair = (to, frm)
            if (frm, to) in counted_pairs or reverse_pair in counted_pairs:
                continue
            counted_pairs.add((frm, to))
            weights.append(float(w))

        avg = sum(weights) / len(weights) if weights else 0.5
        target_record = await self._get_record(db, target)
        if target_record:
            target_record.endorsement_score = round(min(avg, 1.0), 3)
            target_record.trust_score = self._compute_trust_score(target_record)
            target_record.updated_at = utcnow()

    async def _check_anomalies(self, db: AsyncSession, record: TrustRecord) -> None:
        """Sudden success-rate spike after a dormant period."""
        if record.total_tasks < 5 or record.last_computed_at is None:
            return
        if (utcnow() - record.last_computed_at).total_seconds() < 86400 * 7:
            return  # not dormant
        recent = await db.execute(
            select(func.count(Task.id)).where(
                Task.to_agent_id == record.agent_id,
                Task.created_at >= utcnow() - timedelta(hours=1),
            )
        )
        recent_count = recent.scalar() or 0
        if recent_count >= 3:
            await self._emit_anomaly(db, record.agent_id, "success_spike_after_dormancy",
                                     {"recent_tasks_1h": recent_count})

    async def _emit_anomaly(
        self, db: AsyncSession, agent_id: uuid.UUID, anomaly_type: str, payload: dict[str, Any]
    ) -> None:
        await log_audit_event(
            db,
            event_type="anomaly_detected",
            actor_id=agent_id,
            target_id=agent_id,
            target_type="agent",
            payload={"anomaly_type": anomaly_type, **payload},
        )
        try:
            from app.core import nats_client
            await nats_client.publish_event(
                "trust",
                {"type": "anomaly_detected", "agent_id": str(agent_id),
                 "anomaly_type": anomaly_type, **payload},
            )
        except Exception:
            pass  # NATS optional

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

        # Unverified (open) disputes never penalize — penalty only after review.
        # Increment dispute_count for visibility on the review queue size.
        record = await self._get_record(db, reported_agent_id)
        if record:
            record.dispute_count += 1

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

    async def list_disputes(
        self,
        db: AsyncSession,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(Dispute)
        count_query = select(func.count(Dispute.id))
        if status:
            query = query.where(Dispute.status == status)
            count_query = count_query.where(Dispute.status == status)

        total = (await db.execute(count_query)).scalar() or 0
        rows = (await db.execute(
            query.order_by(Dispute.created_at.desc()).offset(offset).limit(limit)
        )).scalars().all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "disputes": [self._dispute_to_dict(d) for d in rows],
        }

    async def resolve_dispute(
        self,
        db: AsyncSession,
        dispute_id: str,
        verdict: str,
        resolution_notes: str | None = None,
        operator_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Resolve a dispute from the review queue.

        verdict: 'valid'   -> resolved_valid: penalty applied, score drops
                 'invalid' -> resolved_invalid: dispute dismissed, penalty restored
                 'withdrawn' -> reporter withdraws the claim
        """
        if verdict not in ("valid", "invalid", "withdrawn"):
            raise ValueError("verdict must be 'valid', 'invalid', or 'withdrawn'")

        result = await db.execute(select(Dispute).where(Dispute.id == uuid.UUID(dispute_id)))
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError("Dispute not found")
        if dispute.status not in ("open", "under_review"):
            raise ValueError(f"Cannot resolve dispute with status '{dispute.status}'")

        new_status = {
            "valid": "resolved_valid",
            "invalid": "resolved_invalid",
            "withdrawn": "withdrawn",
        }[verdict]
        dispute.status = new_status
        dispute.resolution_notes = resolution_notes
        dispute.resolved_by = operator_id
        dispute.reviewed_at = utcnow()
        dispute.verified = True if verdict == "valid" else (False if verdict == "invalid" else None)
        await db.flush()

        record = await self._get_record(db, dispute.reported_agent_id)
        if record:
            if verdict == "valid":
                record.dispute_penalty = round(min(float(record.dispute_penalty) + 0.15, 1.0), 3)
            await log_audit_event(
                db,
                event_type="dispute_resolved",
                actor_id=operator_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                target_id=dispute.reported_agent_id,
                target_type="agent",
                payload={"dispute_id": str(dispute.id), "verdict": verdict},
            )
            record.trust_score = self._compute_trust_score(record)
            record.updated_at = utcnow()

        try:
            from app.core import nats_client
            await nats_client.publish_event(
                "trust",
                {"type": "dispute_resolved", "dispute_id": str(dispute.id),
                 "reported_agent_id": str(dispute.reported_agent_id), "verdict": verdict},
            )
        except Exception:
            pass

        return self._dispute_to_dict(dispute)

    async def mark_dispute_under_review(self, db: AsyncSession, dispute_id: str) -> dict[str, Any]:
        result = await db.execute(select(Dispute).where(Dispute.id == uuid.UUID(dispute_id)))
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError("Dispute not found")
        if dispute.status != "open":
            raise ValueError(f"Cannot mark dispute with status '{dispute.status}' for review")
        dispute.status = "under_review"
        await db.flush()
        return self._dispute_to_dict(dispute)

    def _dispute_to_dict(self, dispute: Dispute) -> dict[str, Any]:
        return {
            "id": str(dispute.id),
            "reported_agent_id": str(dispute.reported_agent_id),
            "reporter_agent_id": str(dispute.reporter_agent_id),
            "task_id": str(dispute.task_id) if dispute.task_id else None,
            "reason": dispute.reason,
            "evidence": dispute.evidence,
            "status": dispute.status,
            "resolution_notes": dispute.resolution_notes,
            "reviewed_at": dispute.reviewed_at.isoformat() if dispute.reviewed_at else None,
            "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
            "updated_at": dispute.updated_at.isoformat() if dispute.updated_at else None,
        }

    async def get_events(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            return []

        events: list[dict[str, Any]] = []

        result = await db.execute(select(TrustRecord).where(TrustRecord.agent_id == resolved))
        record = result.scalar_one_or_none()
        current_score = float(record.trust_score) if record else 0.5

        if record:
            events.append(
                {
                    "event_id": str(record.id),
                    "event_type": "trust_initialized",
                    "score_delta": 0.0,
                    "new_score": current_score,
                    "reference_id": None,
                    "timestamp": record.created_at.isoformat() if record.created_at else None,
                }
            )

        endorsements_result = await db.execute(
            select(Endorsement).where(Endorsement.to_agent_id == resolved).limit(limit)
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

        disputes_result = await db.execute(
            select(Dispute).where(Dispute.reported_agent_id == resolved).limit(limit)
        )
        for dispute in disputes_result.scalars().all():
            events.append(
                {
                    "event_id": str(dispute.id),
                    "event_type": "dispute_filed",
                    "score_delta": -0.1 if dispute.verified is True else 0.0,
                    "new_score": float(record.trust_score),
                    "reference_id": str(dispute.reporter_agent_id),
                    "timestamp": dispute.created_at.isoformat() if dispute.created_at else None,
                }
            )
            if dispute.reviewed_at:
                events.append(
                    {
                        "event_id": str(dispute.id),
                        "event_type": "dispute_resolved",
                        "score_delta": -0.15 if dispute.status == "resolved_valid" else 0.0,
                        "new_score": float(record.trust_score),
                        "reference_id": str(dispute.id),
                        "timestamp": dispute.reviewed_at.isoformat(),
                    }
                )

        # Anomaly events from the audit log (anomaly_detected events target the agent)
        from app.models.audit import AuditEvent
        anomaly_rows = await db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "anomaly_detected",
                AuditEvent.target_id == resolved,
            ).order_by(AuditEvent.occurred_at.desc()).limit(limit)
        )
        for anomaly in anomaly_rows.scalars().all():
            payload = anomaly.payload or {}
            events.append(
                {
                    "event_id": f"anomaly:{anomaly.id}",
                    "event_type": payload.get("anomaly_type", "anomaly_detected"),
                    "score_delta": 0.0,
                    "new_score": current_score,
                    "reference_id": str(anomaly.id),
                    "timestamp": anomaly.occurred_at.isoformat() if anomaly.occurred_at else None,
                }
            )

        return sorted(events, key=lambda x: x.get("timestamp") or "", reverse=True)[:limit]

    def _record_to_dict(self, record: TrustRecord) -> dict[str, Any]:
        return {
            "agent_id": str(record.agent_id),
            "score": float(record.trust_score),
            "components": {
                "task_completion_rate": float(record.outcome_rate),
                "latency_adherence": 0.8,
                "endorsement_score": float(record.endorsement_score),
                "dispute_penalty": float(record.dispute_penalty),
                "age_factor": float(record.age_factor),
            },
            "total_tasks": record.total_tasks,
            "successful_tasks": record.successful_tasks,
            "dispute_count": record.dispute_count,
            "last_active": record.last_computed_at.isoformat() if record.last_computed_at else None,
            "computed_at": record.last_computed_at.isoformat() if record.last_computed_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
