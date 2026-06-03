from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.negotiation import Negotiation


def utcnow() -> datetime:
    return datetime.now(UTC)


class NegotiationService:
    async def create_proposal(
        self,
        db: AsyncSession,
        requester_id: str,
        target_id: str,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        negotiation = Negotiation(
            requester_id=uuid.UUID(requester_id),
            target_id=uuid.UUID(target_id),
            capability=proposal.get("capability", ""),
            status="proposed",
            proposal=proposal,
            session_token=secrets.token_urlsafe(32),
            round_count=1,
            expires_at=utcnow() + timedelta(seconds=proposal.get("ttl_seconds", 300)),
        )
        db.add(negotiation)
        await db.flush()

        return {
            "negotiation_id": str(negotiation.id),
            "status": "proposed",
            "session_token": negotiation.session_token,
            "expires_at": negotiation.expires_at.isoformat(),
            "created_at": negotiation.created_at.isoformat() if negotiation.created_at else None,
        }

    async def respond(
        self,
        db: AsyncSession,
        negotiation_id: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(
            select(Negotiation).where(Negotiation.id == uuid.UUID(negotiation_id))
        )
        negotiation = result.scalar_one_or_none()
        if not negotiation:
            raise ValueError("Negotiation not found")

        if negotiation.status not in ("proposed", "countered"):
            raise ValueError(f"Cannot respond to negotiation in status: {negotiation.status}")

        decision = response.get("decision", "")
        if decision == "accepted":
            negotiation.status = "accepted"
        elif decision == "countered":
            negotiation.status = "countered"
            negotiation.round_count += 1
            if negotiation.round_count > 3:
                raise ValueError("Maximum negotiation rounds exceeded")
        elif decision == "declined":
            negotiation.status = "declined"
        else:
            raise ValueError(f"Invalid decision: {decision}")

        negotiation.response = response
        negotiation.updated_at = utcnow()
        await db.flush()

        return {
            "negotiation_id": str(negotiation.id),
            "status": negotiation.status,
            "session_token": negotiation.session_token
            if negotiation.status == "accepted"
            else None,
            "updated_at": negotiation.updated_at.isoformat(),
        }

    async def get_negotiation(self, db: AsyncSession, negotiation_id: str) -> dict[str, Any] | None:
        result = await db.execute(
            select(Negotiation).where(Negotiation.id == uuid.UUID(negotiation_id))
        )
        negotiation = result.scalar_one_or_none()
        if not negotiation:
            return None
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
