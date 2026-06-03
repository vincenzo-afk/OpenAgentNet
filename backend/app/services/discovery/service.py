from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.trust import TrustRecord


class DiscoveryService:
    async def search(
        self,
        db: AsyncSession,
        capabilities: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = filters or {}
        query = select(Agent).where(Agent.deleted_at.is_(None))
        count_query = select(func.count(Agent.id)).where(Agent.deleted_at.is_(None))

        # Status filter
        status = filters.get("status", "active")
        query = query.where(Agent.status == status)
        count_query = count_query.where(Agent.status == status)

        # Capability filter using JSONB containment
        if capabilities:
            import json as _json

            for cap in capabilities:
                safe_cap = _json.dumps([{"name": cap}])
                query = query.where(Agent.capabilities.op("@>")(sa.text(f"'{safe_cap}'::jsonb")))
                count_query = count_query.where(
                    Agent.capabilities.op("@>")(sa.text(f"'{safe_cap}'::jsonb"))
                )

        # Trust score filter via join
        min_trust = filters.get("min_trust_score")
        if min_trust is not None:
            query = query.join(TrustRecord, TrustRecord.agent_id == Agent.id).where(
                TrustRecord.trust_score >= min_trust
            )
            count_query = count_query.join(TrustRecord, TrustRecord.agent_id == Agent.id).where(
                TrustRecord.trust_score >= min_trust
            )

        # Tag filter
        tags = filters.get("tags")
        if tags:
            for tag in tags:
                query = query.where(Agent.tags.contains([tag]))
                count_query = count_query.where(Agent.tags.contains([tag]))

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Sort
        if sort:
            sort_field, sort_dir = sort.split(":") if ":" in sort else (sort, "desc")
            if sort_field == "trust_score":
                query = query.outerjoin(TrustRecord, TrustRecord.agent_id == Agent.id)
                if sort_dir == "desc":
                    query = query.order_by(TrustRecord.trust_score.desc().nullslast())
                else:
                    query = query.order_by(TrustRecord.trust_score.asc().nullsfirst())
            elif hasattr(Agent, sort_field):
                col = getattr(Agent, sort_field)
                query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())
        else:
            query = query.order_by(Agent.created_at.desc())

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        # Build results with trust scores
        items = []
        for agent in agents:
            trust_result = await db.execute(
                select(TrustRecord).where(TrustRecord.agent_id == agent.id)
            )
            trust = trust_result.scalar_one_or_none()
            cap_names = [c.get("name", "") for c in (agent.capabilities or [])]
            items.append(
                {
                    "agent_id": str(agent.id),
                    "name": agent.name,
                    "display_name": agent.display_name,
                    "version": agent.version,
                    "capabilities": cap_names,
                    "tags": agent.tags or [],
                    "trust_score": float(trust.trust_score) if trust else 0.5,
                    "metadata": agent.metadata_ or {},
                    "status": agent.status,
                }
            )

        return {
            "total": total,
            "agents": items,
            "query_id": str(uuid.uuid4()),
        }

    async def get_similar(
        self, db: AsyncSession, agent_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(Agent).where(
                Agent.id == uuid.UUID(agent_id),
                Agent.deleted_at.is_(None),
            )
        )
        target = result.scalar_one_or_none()
        if not target:
            return []

        # Find agents with overlapping capabilities
        target_caps = [c.get("name", "") for c in (target.capabilities or [])]
        if not target_caps:
            return []

        query = (
            select(Agent)
            .where(
                Agent.id != uuid.UUID(agent_id),
                Agent.deleted_at.is_(None),
                Agent.status == "active",
            )
            .limit(limit)
        )
        result = await db.execute(query)
        agents = result.scalars().all()

        items = []
        for agent in agents:
            cap_names = [c.get("name", "") for c in (agent.capabilities or [])]
            items.append(
                {
                    "agent_id": str(agent.id),
                    "name": agent.name,
                    "display_name": agent.display_name,
                    "capabilities": cap_names,
                }
            )

        return items
