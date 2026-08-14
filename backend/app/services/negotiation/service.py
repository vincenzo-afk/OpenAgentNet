from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.models.negotiation import Negotiation
from app.models.negotiation_round import NegotiationRound

# Phase 3 state machine: proposed -> countered <-> (counter loops) -> accepted | declined | expired
# Only the negotiation TARGET may accept, counter, or decline. The requester created it.
VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "proposed": ("countered", "accepted", "declined", "expired"),
    "countered": ("countered", "accepted", "declined", "expired"),
    "accepted": (),
    "declined": (),
    "expired": (),
}

MAX_ROUNDS = 3


def utcnow() -> datetime:
    return datetime.now(UTC)


def _neg_to_dict(negotiation: Negotiation) -> dict[str, Any]:
    return {
        "id": str(negotiation.id),
        "requester_id": str(negotiation.requester_id),
        "target_id": str(negotiation.target_id),
        "capability": negotiation.capability,
        "status": negotiation.status,
        "proposal": negotiation.proposal,
        "response": negotiation.response,
        "session_token": negotiation.session_token,
        "round_count": negotiation.round_count,
        "expires_at": negotiation.expires_at.isoformat(),
        "created_at": negotiation.created_at.isoformat() if negotiation.created_at else None,
    }


def _round_to_dict(round_: NegotiationRound) -> dict[str, Any]:
    return {
        "id": round_.id,
        "round_number": round_.round_number,
        "actor_id": str(round_.actor_id),
        "role": round_.role,
        "decision": round_.decision,
        "proposal": round_.proposal,
        "occurred_at": round_.occurred_at.isoformat() if round_.occurred_at else None,
    }


async def _emit_negotiation_event(event_type: str, negotiation: Negotiation, extra: dict[str, Any] | None = None) -> None:
    try:
        from app.core import nats_client

        await nats_client.publish_event(
            "negotiation",
            {
                "type": event_type,
                "negotiation_id": str(negotiation.id),
                "requester_id": str(negotiation.requester_id),
                "target_id": str(negotiation.target_id),
                "capability": negotiation.capability,
                "status": negotiation.status,
                **(extra or {}),
            },
        )
    except Exception:
        pass  # NATS is optional


class NegotiationService:
    async def create_proposal(
        self,
        db: AsyncSession,
        requester_id: str,
        target_id: str,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        req_uuid = parse_agent_id(requester_id)
        tgt_uuid = parse_agent_id(target_id)
        if not req_uuid or not tgt_uuid or req_uuid == tgt_uuid:
            raise ValueError("Invalid or identical agent ids")

        negotiation = Negotiation(
            requester_id=req_uuid,
            target_id=tgt_uuid,
            capability=proposal.get("capability", ""),
            status="proposed",
            proposal=proposal,
            session_token=secrets.token_urlsafe(32),
            round_count=1,
            expires_at=utcnow() + timedelta(seconds=proposal.get("ttl_seconds", 300)),
        )
        db.add(negotiation)
        await db.flush()

        round_ = NegotiationRound(
            negotiation_id=negotiation.id,
            round_number=1,
            actor_id=req_uuid,
            role="requester",
            decision="proposed",
            proposal=proposal,
        )
        db.add(round_)
        await db.flush()

        await _emit_negotiation_event("negotiation_created", negotiation)

        return {
            "negotiation_id": str(negotiation.id),
            "status": "proposed",
            "session_token": negotiation.session_token,
            "expires_at": negotiation.expires_at.isoformat(),
            "created_at": negotiation.created_at.isoformat() if negotiation.created_at else None,
        }

    async def _expire_due(self, db: AsyncSession) -> int:
        """Mark open negotiations whose TTL has passed as expired (Phase 3 auto-expiry)."""
        result = await db.execute(
            select(Negotiation).where(
                Negotiation.status.in_(("proposed", "countered")),
                Negotiation.expires_at < utcnow(),
            )
        )
        count = 0
        for negotiation in result.scalars().all():
            negotiation.status = "expired"
            negotiation.updated_at = utcnow()
            count += 1
        if count:
            await db.flush()
        return count

    async def respond(
        self,
        db: AsyncSession,
        negotiation_id: str,
        response: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        # Phase 3: auto-expire anything past its TTL before processing.
        await self._expire_due(db)

        try:
            neg_uuid = uuid.UUID(negotiation_id)
        except (ValueError, AttributeError):
            raise ValueError("Invalid negotiation id")

        result = await db.execute(select(Negotiation).where(Negotiation.id == neg_uuid))
        negotiation = result.scalar_one_or_none()
        if not negotiation:
            raise ValueError("Negotiation not found")

        actor_uuid = parse_agent_id(actor_id)
        if not actor_uuid or actor_uuid not in (negotiation.requester_id, negotiation.target_id):
            raise ValueError("Only negotiation participants may respond")

        role = "requester" if actor_uuid == negotiation.requester_id else "target"

        if negotiation.status not in VALID_TRANSITIONS:
            raise ValueError(f"Negotiation is in a terminal status: {negotiation.status}")

        decision = response.get("decision", "")
        if decision not in VALID_TRANSITIONS.get(negotiation.status, ()):
            raise ValueError(
                f"Invalid transition: {negotiation.status} -> {decision}"
            )

        round_number = negotiation.round_count + 1 if decision == "countered" else negotiation.round_count

        if decision == "accepted":
            negotiation.status = "accepted"
            negotiation.session_token = secrets.token_urlsafe(32)
        elif decision == "countered":
            negotiation.status = "countered"
            negotiation.round_count += 1
            if negotiation.round_count > MAX_ROUNDS:
                raise ValueError("Maximum negotiation rounds exceeded")
            negotiation.expires_at = utcnow() + timedelta(
                seconds=max(60, negotiation.proposal.get("ttl_seconds", 300))
            )
        elif decision == "declined":
            negotiation.status = "declined"
        else:
            raise ValueError(f"Invalid decision: {decision}")

        # Store the full counter-proposal or agreed constraints with the response.
        negotiation.response = response
        negotiation.updated_at = utcnow()

        db.add(
            NegotiationRound(
                negotiation_id=negotiation.id,
                round_number=round_number,
                actor_id=actor_uuid,
                role=role,
                decision=decision,
                proposal={k: v for k, v in response.items() if k != "decision"},
            )
        )
        await db.flush()

        await _emit_negotiation_event(
            f"negotiation_{decision}d",
            negotiation,
            {"actor_id": str(actor_uuid), "round": round_number},
        )

        return {
            "negotiation_id": str(negotiation.id),
            "status": negotiation.status,
            "session_token": negotiation.session_token if negotiation.status == "accepted" else None,
            "round_number": round_number,
            "updated_at": negotiation.updated_at.isoformat(),
        }

    async def get_negotiation(self, db: AsyncSession, negotiation_id: str) -> dict[str, Any] | None:
        try:
            neg_uuid = uuid.UUID(negotiation_id)
        except (ValueError, AttributeError):
            return None

        result = await db.execute(select(Negotiation).where(Negotiation.id == neg_uuid))
        negotiation = result.scalar_one_or_none()
        if not negotiation:
            return None

        rounds_result = await db.execute(
            select(NegotiationRound)
            .where(NegotiationRound.negotiation_id == negotiation.id)
            .order_by(NegotiationRound.round_number)
        )
        rounds = [_round_to_dict(r) for r in rounds_result.scalars().all()]

        data = _neg_to_dict(negotiation)
        data["rounds"] = rounds
        return data

    async def list_negotiations(
        self,
        db: AsyncSession,
        agent_id: str,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Invalid agent id")

        query = select(Negotiation).where(
            (Negotiation.requester_id == resolved) | (Negotiation.target_id == resolved)
        )
        if status_filter:
            query = query.where(Negotiation.status == status_filter)
        query = query.order_by(Negotiation.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        items = [_neg_to_dict(n) for n in result.scalars().all()]

        count_query = select(Negotiation.id).where(
            (Negotiation.requester_id == resolved) | (Negotiation.target_id == resolved)
        )
        if status_filter:
            count_query = count_query.where(Negotiation.status == status_filter)
        total = (await db.execute(count_query)).scalars().all().__len__()

        return {"total": total, "limit": limit, "offset": offset, "negotiations": items}
