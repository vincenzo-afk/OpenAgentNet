from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.core.nats_client import publish_event
from app.models.agent import Agent
from app.models.team import Team, TeamMember


def utcnow() -> datetime:
    return datetime.now(UTC)


class TeamService:
    async def create_team(
        self, db: AsyncSession, owner_agent_id: str, name: str, description: str | None, member_agent_ids: list[str]
    ) -> dict[str, Any]:
        owner_id = parse_agent_id(owner_agent_id)
        if owner_id is None:
            raise ValueError("Invalid owner_agent_id")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Team name is required")
        existing_result = await db.execute(
            select(Team).where(Team.owner_agent_id == owner_id, Team.name == clean_name)
        )
        if existing_result.scalar_one_or_none():
            raise ValueError("Team name already exists for this owner")

        member_ids = {owner_id}
        for raw_id in member_agent_ids:
            agent_id = parse_agent_id(raw_id)
            if agent_id is None:
                raise ValueError(f"Invalid member agent_id: {raw_id}")
            member_ids.add(agent_id)
        if member_ids - {owner_id}:
            active_result = await db.execute(
                select(Agent.id).where(Agent.id.in_(member_ids - {owner_id}), Agent.status == "active")
            )
            active_ids = set(active_result.scalars().all())
            missing = member_ids - {owner_id} - active_ids
            if missing:
                raise ValueError("All team members must be active registered agents")

        team = Team(name=clean_name, description=description, owner_agent_id=owner_id, status="active")
        db.add(team)
        await db.flush()
        for agent_id in member_ids:
            db.add(TeamMember(team_id=team.id, agent_id=agent_id, role="owner" if agent_id == owner_id else "member"))
        await db.flush()
        await publish_event(
            "team.created",
            {"team_id": str(team.id), "owner_agent_id": str(owner_id), "name": team.name},
        )
        return await self._team_to_dict(db, team)

    async def get_team(self, db: AsyncSession, team_id: str) -> dict[str, Any] | None:
        team = await self._load_team(db, team_id)
        return await self._team_to_dict(db, team) if team else None

    async def list_teams(
        self, db: AsyncSession, limit: int = 20, offset: int = 0, status: str = "active"
    ) -> dict[str, Any]:
        count_result = await db.execute(select(func.count(Team.id)).where(Team.status == status))
        total = count_result.scalar() or 0
        result = await db.execute(
            select(Team).where(Team.status == status).order_by(Team.created_at.desc()).offset(offset).limit(limit)
        )
        teams = result.scalars().all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [await self._team_to_dict(db, team) for team in teams],
        }

    async def add_member(
        self, db: AsyncSession, team_id: str, owner_agent_id: str, member_agent_id: str
    ) -> dict[str, Any]:
        team = await self._require_team(db, team_id)
        self._authorize_owner(team, owner_agent_id)
        member_id = parse_agent_id(member_agent_id)
        if member_id is None:
            raise ValueError("Invalid member agent_id")
        agent_result = await db.execute(
            select(Agent).where(Agent.id == member_id, Agent.status == "active")
        )
        if not agent_result.scalar_one_or_none():
            raise ValueError("Member must be an active registered agent")
        existing_result = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.agent_id == member_id)
        )
        if existing_result.scalar_one_or_none():
            raise ValueError("Agent is already a team member")
        db.add(TeamMember(team_id=team.id, agent_id=member_id, role="member"))
        team.updated_at = utcnow()
        await db.flush()
        await publish_event(
            "team.member_added",
            {"team_id": str(team.id), "agent_id": str(member_id), "owner_agent_id": str(team.owner_agent_id)},
        )
        return await self._team_to_dict(db, team)

    async def remove_member(
        self, db: AsyncSession, team_id: str, owner_agent_id: str, member_agent_id: str
    ) -> dict[str, Any]:
        team = await self._require_team(db, team_id)
        self._authorize_owner(team, owner_agent_id)
        member_id = parse_agent_id(member_agent_id)
        if member_id is None:
            raise ValueError("Invalid member agent_id")
        if member_id == team.owner_agent_id:
            raise ValueError("Team owner cannot be removed")
        result = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.agent_id == member_id)
        )
        member = result.scalar_one_or_none()
        if not member:
            raise ValueError("Agent is not a team member")
        await db.delete(member)
        team.updated_at = utcnow()
        await db.flush()
        await publish_event(
            "team.member_removed",
            {"team_id": str(team.id), "agent_id": str(member_id), "owner_agent_id": str(team.owner_agent_id)},
        )
        return await self._team_to_dict(db, team)

    async def _load_team(self, db: AsyncSession, team_id: str) -> Team | None:
        try:
            parsed_id = uuid.UUID(team_id)
        except ValueError as exc:
            raise ValueError("Invalid team_id") from exc
        result = await db.execute(select(Team).where(Team.id == parsed_id))
        return result.scalar_one_or_none()

    async def _require_team(self, db: AsyncSession, team_id: str) -> Team:
        team = await self._load_team(db, team_id)
        if team is None:
            raise ValueError("Team not found")
        if team.status != "active":
            raise ValueError("Team is not active")
        return team

    @staticmethod
    def _authorize_owner(team: Team, owner_agent_id: str) -> None:
        if parse_agent_id(owner_agent_id) != team.owner_agent_id:
            raise PermissionError("Only the team owner may manage membership")

    async def _team_to_dict(self, db: AsyncSession, team: Team) -> dict[str, Any]:
        result = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team.id).order_by(TeamMember.joined_at.asc())
        )
        members = result.scalars().all()
        return {
            "id": str(team.id),
            "name": team.name,
            "description": team.description,
            "owner_agent_id": str(team.owner_agent_id),
            "status": team.status,
            "members": [
                {
                    "agent_id": str(member.agent_id),
                    "role": member.role,
                    "joined_at": member.joined_at,
                }
                for member in members
            ],
            "created_at": team.created_at,
            "updated_at": team.updated_at,
        }
