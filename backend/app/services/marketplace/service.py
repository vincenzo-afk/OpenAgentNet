from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace import MarketplaceListing


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceService:
    async def create_listing(
        self,
        db: AsyncSession,
        agent_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        # Check if agent already has a listing
        existing = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == uuid.UUID(agent_id))
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has a marketplace listing")

        listing = MarketplaceListing(
            agent_id=uuid.UUID(agent_id),
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
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(MarketplaceListing).where(MarketplaceListing.is_public.is_(True))
        count_query = select(func.count(MarketplaceListing.id)).where(
            MarketplaceListing.is_public.is_(True)
        )

        # Filter by capability if provided (search in agent's capabilities via join)
        if capability:
            from app.models.agent import Agent

            query = query.join(Agent, MarketplaceListing.agent_id == Agent.id).where(
                Agent.capabilities.op("@>")(f'[{{"name": "{capability}"}}]')
            )
            count_query = count_query.join(Agent, MarketplaceListing.agent_id == Agent.id).where(
                Agent.capabilities.op("@>")(f'[{{"name": "{capability}"}}]')
            )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(MarketplaceListing.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        listings = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._listing_to_dict(l) for l in listings],
        }

    async def update_listing(
        self,
        db: AsyncSession,
        agent_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(
            select(MarketplaceListing).where(MarketplaceListing.agent_id == uuid.UUID(agent_id))
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
            select(MarketplaceListing).where(MarketplaceListing.agent_id == uuid.UUID(agent_id))
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise ValueError("No marketplace listing found for this agent")
        await db.delete(listing)
        await db.flush()

    def _listing_to_dict(self, listing: MarketplaceListing) -> dict[str, Any]:
        return {
            "id": str(listing.id),
            "agent_id": str(listing.agent_id),
            "title": listing.title,
            "long_description": listing.long_description,
            "pricing": listing.pricing,
            "sla": listing.sla,
            "tiers": listing.tiers,
            "is_public": listing.is_public,
            "is_featured": listing.is_featured,
            "view_count": listing.view_count,
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
            "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
        }
