from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.models.agent import Agent
from app.models.marketplace import MarketplaceListing, MarketplaceUsage
from app.models.trust import TrustRecord
from app.core.nats_client import publish_event

VALID_ACCESS_TIERS = ("free", "paid", "invite_only")


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
