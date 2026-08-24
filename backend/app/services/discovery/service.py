from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.capability_index import candidate_ids
from app.core.identifiers import parse_agent_id
from app.models.agent import Agent
from app.models.team import Team, TeamMember
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

        # Redis is a hot candidate index; a valid empty result means no agent
        # satisfies the indexed capability intersection. Only None indicates
        # that Redis was unavailable and PostgreSQL should be used as fallback.
        indexed_ids = await candidate_ids(
            capabilities or [],
            min_trust_score=filters.get("min_trust_score"),
        )
        if indexed_ids is not None:
            query = query.where(Agent.id.in_(indexed_ids))
            count_query = count_query.where(Agent.id.in_(indexed_ids))

        # Status filter
        status = filters.get("status", "active")
        query = query.where(Agent.status == status)
        count_query = count_query.where(Agent.status == status)

        # Region filter supports local, remote, and federated registry views.
        region = filters.get("region")
        if region:
            query = query.where(Agent.region == region)
            count_query = count_query.where(Agent.region == region)

        # Capability filter using JSONB containment
        if capabilities:
            import json as _json

            for cap in capabilities:
                safe_cap = [{"name": cap}]
                from sqlalchemy.dialects.postgresql import JSONB
                query = query.where(Agent.capabilities.op("@>")(sa.cast(safe_cap, JSONB)))
                count_query = count_query.where(
                    Agent.capabilities.op("@>")(sa.cast(safe_cap, JSONB))
                )

        # Trust score filter via join
        trust_joined = False
        min_trust = filters.get("min_trust_score")
        if min_trust is not None:
            trust_joined = True
            query = query.join(TrustRecord, TrustRecord.agent_id == Agent.id).where(
                TrustRecord.trust_score >= min_trust
            )
            count_query = count_query.join(TrustRecord, TrustRecord.agent_id == Agent.id).where(
                TrustRecord.trust_score >= min_trust
            )

        # P95 latency filter uses the normalized metadata fields exposed by
        # registered agents. Unknown latency is excluded from bounded searches.
        max_latency = filters.get("max_latency_p95_ms")
        latency_expr = func.coalesce(
            cast(Agent.metadata_["latency_p95_ms"].astext, Numeric),
            cast(Agent.metadata_["latency_estimate_ms"].astext, Numeric),
        )
        cost_expr = func.coalesce(
            cast(Agent.metadata_["cost"].astext, Numeric),
            cast(Agent.metadata_["cost_estimate"]["value"].astext, Numeric),
        )
        if max_latency is not None:
            query = query.where(latency_expr <= max_latency)
            count_query = count_query.where(latency_expr <= max_latency)

        # Exclude explicitly listed agents from both result and count queries.
        excluded_ids = [parse_agent_id(value) for value in filters.get("exclude", [])]
        excluded_ids = [value for value in excluded_ids if value]
        if excluded_ids:
            query = query.where(Agent.id.not_in(excluded_ids))
            count_query = count_query.where(Agent.id.not_in(excluded_ids))

        # Protocol-level language and arbitrary metadata filters are stored in
        # the agent metadata JSONB column and use parameterized JSON operators.
        language = filters.get("language")
        if language:
            language_expr = Agent.metadata_["language"].astext == language
            query = query.where(language_expr)
            count_query = count_query.where(language_expr)
        for key, value in (filters.get("metadata") or {}).items():
            if isinstance(key, str) and value is not None:
                metadata_expr = Agent.metadata_[key].astext == str(value)
                query = query.where(metadata_expr)
                count_query = count_query.where(metadata_expr)

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
            sort_field, sort_dir = sort.split(":", 1) if ":" in sort else (sort, "desc")
            sort_field = {"latency": "latency_p95_ms", "registered": "registered_at"}.get(sort_field, sort_field)
            sort_dir = sort_dir.lower() if sort_dir.lower() in {"asc", "desc"} else "desc"
            if sort_field == "trust_score":
                if not trust_joined:
                    query = query.outerjoin(TrustRecord, TrustRecord.agent_id == Agent.id)
                if sort_dir == "desc":
                    query = query.order_by(TrustRecord.trust_score.desc().nullslast())
                else:
                    query = query.order_by(TrustRecord.trust_score.asc().nullsfirst())
            elif sort_field == "latency_p95_ms":
                query = query.order_by(
                    latency_expr.desc().nullslast()
                    if sort_dir == "desc"
                    else latency_expr.asc().nullsfirst()
                )
            elif sort_field == "cost":
                query = query.order_by(
                    cost_expr.desc().nullslast()
                    if sort_dir == "desc"
                    else cost_expr.asc().nullsfirst()
                )
            elif sort_field == "registered_at":
                query = query.order_by(
                    Agent.created_at.desc() if sort_dir == "desc" else Agent.created_at.asc()
                )
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
                    "region": agent.region,
                    "is_federated": agent.is_federated,
                    "origin_registry_id": agent.origin_registry_id,
                }
            )

        team_query = (
            select(Team, func.count(TeamMember.agent_id).label("member_count"))
            .join(TeamMember, TeamMember.team_id == Team.id)
            .join(Agent, Agent.id == TeamMember.agent_id)
            .where(
                Team.status == "active",
                Agent.status == "active",
                Agent.deleted_at.is_(None),
            )
            .group_by(Team.id)
        )
        for capability in capabilities or []:
            safe_cap = [{"name": capability}]
            member_match = (
                select(TeamMember.team_id)
                .join(Agent, Agent.id == TeamMember.agent_id)
                .where(
                    TeamMember.team_id == Team.id,
                    Agent.status == "active",
                    Agent.deleted_at.is_(None),
                    Agent.capabilities.op("@>")(sa.cast(safe_cap, JSONB)),
                )
            )
            team_query = team_query.where(sa.exists(member_match))
        team_rows = (await db.execute(team_query)).all()
        teams = [
            {
                "team_id": str(team.id),
                "name": team.name,
                "description": team.description,
                "owner_agent_id": str(team.owner_agent_id),
                "status": team.status,
                "member_count": int(member_count),
            }
            for team, member_count in team_rows
        ]

        return {
            "total": total,
            "agents": items,
            "teams": teams,
            "query_id": str(uuid.uuid4()),
        }

    async def get_similar(
        self, db: AsyncSession, agent_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(Agent).where(
                Agent.id == parse_agent_id(agent_id),
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
                Agent.id != parse_agent_id(agent_id),
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
