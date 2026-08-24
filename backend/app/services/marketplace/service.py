from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.models.agent import Agent
from app.models.marketplace import MarketplaceEscrow, MarketplaceListing, MarketplaceUsage
from app.models.task import Task
from app.models.trust import TrustRecord
from app.core.nats_client import publish_event

VALID_ACCESS_TIERS = ("free", "paid", "invite_only")
ESCROW_STATUSES = ("held", "released", "refunded", "disputed")
COMPLETED_TASK_STATUSES = ("success",)


def utcnow() -> datetime:
    return datetime.now(UTC)


class MarketplaceService:
    async def create_listing(
        self,
        db: AsyncSession,
        agent_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        # Check if agent already has a listing
        existing = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == parse_agent_id(agent_id))
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has a marketplace listing")

        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Invalid agent_id")
        listing = MarketplaceListing(
            agent_id=resolved,
            title=data["title"],
            long_description=data.get("long_description"),
            pricing=data.get("pricing", {}),
            sla=data.get("sla", {}),
            tiers=data.get("tiers", []),
            is_public=data.get("is_public", True),
        )
        db.add(listing)
        await db.flush()
        return self._listing_to_dict(listing)

    async def get_listing(self, db: AsyncSession, listing_id: str) -> dict[str, Any] | None:
        result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.id == uuid.UUID(listing_id))
        )
        listing = result.scalar_one_or_none()
        if not listing:
            return None
        return self._listing_to_dict(listing)

    async def search_listings(
        self,
        db: AsyncSession,
        capability: str | None = None,
        min_trust_score: float | None = None,
        access_tier: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        max_latency_p95_ms: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(MarketplaceListing).where(MarketplaceListing.is_public.is_(True))
        count_query = select(func.count(MarketplaceListing.id)).where(
            MarketplaceListing.is_public.is_(True)
        )

        def apply_filters(statement):
            if access_tier:
                statement = statement.where(MarketplaceListing.access_tier == access_tier)

            if capability or min_trust_score is not None:
                statement = statement.join(Agent, MarketplaceListing.agent_id == Agent.id)

            if capability:
                import sqlalchemy as sa
                from sqlalchemy.dialects.postgresql import JSONB

                safe_cap = [{"name": capability}]
                statement = statement.where(Agent.capabilities.op("@>")(sa.cast(safe_cap, JSONB)))

            if min_trust_score is not None:
                statement = statement.join(TrustRecord, MarketplaceListing.agent_id == TrustRecord.agent_id)
                statement = statement.where(TrustRecord.trust_score >= min_trust_score)

            if min_price is not None or max_price is not None:
                price = func.coalesce(
                    cast(MarketplaceListing.pricing["amount"].astext, Numeric),
                    cast(MarketplaceListing.pricing["price"].astext, Numeric),
                )
                if min_price is not None:
                    statement = statement.where(price >= min_price)
                if max_price is not None:
                    statement = statement.where(price <= max_price)

            if max_latency_p95_ms is not None:
                latency = func.coalesce(
                    cast(MarketplaceListing.sla["p95_latency_ms"].astext, Numeric),
                    cast(MarketplaceListing.sla["latency_p95_ms"].astext, Numeric),
                )
                statement = statement.where(latency <= max_latency_p95_ms)

            return statement

        query = apply_filters(query)
        count_query = apply_filters(count_query)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(MarketplaceListing.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        listings = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._listing_to_dict(listing) for listing in listings],
        }

    async def update_listing(
        self,
        db: AsyncSession,
        agent_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == parse_agent_id(agent_id))
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise ValueError("No marketplace listing found for this agent")

        for key, value in data.items():
            if value is not None and hasattr(listing, key):
                setattr(listing, key, value)

        listing.updated_at = utcnow()
        await db.flush()
        return self._listing_to_dict(listing)

    async def delete_listing(self, db: AsyncSession, agent_id: str) -> None:
        result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == parse_agent_id(agent_id))
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise ValueError("No marketplace listing found for this agent")
        await db.delete(listing)
        await db.flush()

    async def set_access_tier(
        self,
        db: AsyncSession,
        agent_id: str,
        access_tier: str,
        tier_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if access_tier not in VALID_ACCESS_TIERS:
            raise ValueError(
                f"Invalid access tier: {access_tier}. Must be one of {', '.join(VALID_ACCESS_TIERS)}"
            )
        result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == parse_agent_id(agent_id))
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise ValueError("No marketplace listing found for this agent")
        listing.access_tier = access_tier
        if tier_details is not None:
            listing.tier_details = tier_details
        listing.updated_at = utcnow()
        await db.flush()
        await db.commit()
        await publish_event(
            "marketplace.tier_changed",
            {
                "listing_id": str(listing.id),
                "agent_id": str(listing.agent_id),
                "access_tier": access_tier,
            },
        )
        return self._listing_to_dict(listing)

    async def record_usage(
        self,
        db: AsyncSession,
        listing_id: str,
        agent_id: str,
        calls: int = 1,
    ) -> dict[str, Any]:
        listing_result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.id == uuid.UUID(listing_id))
        )
        listing = listing_result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Invalid agent_id")
        usage_result = await db.execute(
            select(MarketplaceUsage).where(
                MarketplaceUsage.listing_id == listing.id,
                MarketplaceUsage.agent_id == resolved,
            )
        )
        usage = usage_result.scalar_one_or_none()
        if usage is None:
            usage = MarketplaceUsage(listing_id=listing.id, agent_id=resolved, calls=calls)
            db.add(usage)
            await db.flush()
            u_calls = calls
        else:
            # Capture attributes immediately after flush before further awaits
            u_calls = usage.calls + calls
            usage.calls = u_calls
            usage.last_used_at = utcnow()
            await db.flush()
            # Re-read to return a fresh row consistent with the committed state
            result = await db.execute(
                select(MarketplaceUsage).where(MarketplaceUsage.id == usage.id)
            )
            usage = result.scalar_one()
            u_calls = usage.calls
        await db.commit()
        await publish_event(
            "marketplace.usage",
            {
                "listing_id": listing_id,
                "agent_id": str(resolved),
                "calls": u_calls,
            },
        )
        return {"listing_id": listing_id, "agent_id": str(resolved), "calls": u_calls}

    async def get_metering(
        self,
        db: AsyncSession,
        listing_id: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        listing_result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.id == uuid.UUID(listing_id))
        )
        listing = listing_result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")
        query = select(MarketplaceUsage).where(MarketplaceUsage.listing_id == listing.id)
        if agent_id:
            query = query.where(MarketplaceUsage.agent_id == parse_agent_id(agent_id))
        result = await db.execute(query)
        rows = result.scalars().all()
        return {
            "listing_id": listing_id,
            "access_tier": listing.access_tier,
            "items": [
                {
                    "agent_id": str(row.agent_id),
                    "calls": row.calls,
                    "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
                }
                for row in rows
            ],
        }

    async def create_escrow(
        self,
        db: AsyncSession,
        buyer_agent_id: str,
        listing_id: str,
        amount: Decimal | str | float,
        currency: str = "USD",
        task_id: str | None = None,
        provider_reference: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        buyer_id = parse_agent_id(buyer_agent_id)
        if not buyer_id:
            raise ValueError("Invalid buyer_agent_id")
        try:
            normalized_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("amount must be a valid decimal") from exc
        if normalized_amount <= 0:
            raise ValueError("amount must be greater than zero")
        normalized_currency = currency.strip().upper()
        if not normalized_currency or len(normalized_currency) > 12 or not normalized_currency.isalnum():
            raise ValueError("currency must be 1-12 alphanumeric characters")

        try:
            listing_uuid = uuid.UUID(listing_id)
        except ValueError as exc:
            raise ValueError("Invalid listing_id") from exc
        listing_result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.id == listing_uuid)
        )
        listing = listing_result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")
        if listing.agent_id == buyer_id:
            raise ValueError("Buyer cannot escrow funds for its own listing")

        task_uuid = None
        if task_id:
            try:
                task_uuid = uuid.UUID(task_id)
            except ValueError as exc:
                raise ValueError("Invalid task_id") from exc
            task_result = await db.execute(select(Task).where(Task.id == task_uuid))
            task = task_result.scalar_one_or_none()
            if not task:
                raise ValueError("Task not found")
            if task.from_agent_id != buyer_id or task.to_agent_id != listing.agent_id:
                raise ValueError("Task participants do not match escrow participants")

        if idempotency_key:
            existing_result = await db.execute(
                select(MarketplaceEscrow).where(MarketplaceEscrow.idempotency_key == idempotency_key)
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                if (
                    existing.buyer_agent_id != buyer_id
                    or existing.listing_id != listing.id
                    or existing.amount != normalized_amount
                    or existing.currency != normalized_currency
                ):
                    raise ValueError("Idempotency key is already associated with a different escrow")
                return self._escrow_to_dict(existing)

        escrow = MarketplaceEscrow(
            listing_id=listing.id,
            buyer_agent_id=buyer_id,
            seller_agent_id=listing.agent_id,
            task_id=task_uuid,
            amount=normalized_amount,
            currency=normalized_currency,
            status="held",
            provider_reference=provider_reference,
            idempotency_key=idempotency_key,
            metadata_=metadata or {},
        )
        db.add(escrow)
        await db.flush()
        await publish_event("marketplace.escrow.held", self._escrow_event(escrow))
        return self._escrow_to_dict(escrow)

    async def get_escrow(self, db: AsyncSession, escrow_id: str) -> dict[str, Any] | None:
        escrow = await self._load_escrow(db, escrow_id)
        return self._escrow_to_dict(escrow) if escrow else None

    async def release_escrow(
        self, db: AsyncSession, escrow_id: str, actor_agent_id: str
    ) -> dict[str, Any]:
        escrow = await self._require_escrow(db, escrow_id, for_update=True)
        self._authorize_escrow_participant(escrow, actor_agent_id)
        if escrow.status != "held":
            raise ValueError(f"Escrow cannot be released from status '{escrow.status}'")
        if escrow.task_id:
            task_result = await db.execute(select(Task).where(Task.id == escrow.task_id))
            task = task_result.scalar_one_or_none()
            if not task or task.status not in COMPLETED_TASK_STATUSES:
                raise ValueError("Escrow can only be released after successful task completion")
        escrow.status = "released"
        escrow.settled_at = utcnow()
        escrow.updated_at = utcnow()
        await db.flush()
        await publish_event("marketplace.escrow.released", self._escrow_event(escrow))
        return self._escrow_to_dict(escrow)

    async def dispute_escrow(
        self,
        db: AsyncSession,
        escrow_id: str,
        actor_agent_id: str,
        reason: str,
    ) -> dict[str, Any]:
        escrow = await self._require_escrow(db, escrow_id, for_update=True)
        self._authorize_escrow_participant(escrow, actor_agent_id)
        if escrow.status != "held":
            raise ValueError(f"Escrow cannot be disputed from status '{escrow.status}'")
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValueError("reason is required")
        escrow.status = "disputed"
        escrow.updated_at = utcnow()
        metadata = dict(escrow.metadata_ or {})
        metadata["dispute_reason"] = clean_reason
        metadata["disputed_by"] = str(parse_agent_id(actor_agent_id))
        metadata["disputed_at"] = escrow.updated_at.isoformat()
        escrow.metadata_ = metadata
        await db.flush()
        await publish_event("marketplace.escrow.disputed", self._escrow_event(escrow))
        return self._escrow_to_dict(escrow)

    async def refund_escrow(
        self,
        db: AsyncSession,
        escrow_id: str,
        reason: str,
        actor_agent_id: str | None = None,
    ) -> dict[str, Any]:
        escrow = await self._require_escrow(db, escrow_id, for_update=True)
        if escrow.status not in ("held", "disputed"):
            raise ValueError(f"Escrow cannot be refunded from status '{escrow.status}'")
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValueError("reason is required")
        escrow.status = "refunded"
        escrow.settled_at = utcnow()
        escrow.updated_at = utcnow()
        metadata = dict(escrow.metadata_ or {})
        metadata["refund_reason"] = clean_reason
        if actor_agent_id:
            metadata["refunded_by"] = str(parse_agent_id(actor_agent_id) or actor_agent_id)
        metadata["refunded_at"] = escrow.updated_at.isoformat()
        escrow.metadata_ = metadata
        await db.flush()
        await publish_event("marketplace.escrow.refunded", self._escrow_event(escrow))
        return self._escrow_to_dict(escrow)

    async def _load_escrow(
        self, db: AsyncSession, escrow_id: str, for_update: bool = False
    ) -> MarketplaceEscrow | None:
        try:
            escrow_uuid = uuid.UUID(escrow_id)
        except ValueError as exc:
            raise ValueError("Invalid escrow_id") from exc
        statement = select(MarketplaceEscrow).where(MarketplaceEscrow.id == escrow_uuid)
        if for_update:
            statement = statement.with_for_update()
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    async def _require_escrow(
        self, db: AsyncSession, escrow_id: str, for_update: bool = False
    ) -> MarketplaceEscrow:
        escrow = await self._load_escrow(db, escrow_id, for_update=for_update)
        if not escrow:
            raise ValueError("Escrow not found")
        return escrow

    @staticmethod
    def _authorize_escrow_participant(escrow: MarketplaceEscrow, actor_agent_id: str) -> None:
        actor_id = parse_agent_id(actor_agent_id)
        if not actor_id or actor_id not in (escrow.buyer_agent_id, escrow.seller_agent_id):
            raise PermissionError("Only the escrow buyer or seller may mutate this escrow")

    @staticmethod
    def _escrow_event(escrow: MarketplaceEscrow) -> dict[str, Any]:
        return {
            "escrow_id": str(escrow.id),
            "listing_id": str(escrow.listing_id),
            "buyer_agent_id": str(escrow.buyer_agent_id),
            "seller_agent_id": str(escrow.seller_agent_id),
            "task_id": str(escrow.task_id) if escrow.task_id else None,
            "amount": str(escrow.amount),
            "currency": escrow.currency,
            "status": escrow.status,
        }

    @staticmethod
    def _escrow_to_dict(escrow: MarketplaceEscrow) -> dict[str, Any]:
        return {
            **MarketplaceService._escrow_event(escrow),
            "provider_reference": escrow.provider_reference,
            "idempotency_key": escrow.idempotency_key,
            "metadata": escrow.metadata_ or {},
            "created_at": escrow.created_at.isoformat() if escrow.created_at else None,
            "updated_at": escrow.updated_at.isoformat() if escrow.updated_at else None,
            "settled_at": escrow.settled_at.isoformat() if escrow.settled_at else None,
        }

    def _listing_to_dict(self, listing: MarketplaceListing) -> dict[str, Any]:
        return {
            "id": str(listing.id),
            "agent_id": str(listing.agent_id),
            "title": listing.title,
            "long_description": listing.long_description,
            "pricing": listing.pricing,
            "sla": listing.sla,
            "tiers": listing.tiers,
            "access_tier": listing.access_tier,
            "tier_details": listing.tier_details,
            "is_public": listing.is_public,
            "is_featured": listing.is_featured,
            "view_count": listing.view_count,
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
            "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
        }
