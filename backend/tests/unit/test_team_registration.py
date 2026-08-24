from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.agent import Agent
from app.models.team import Team, TeamMember
from app.services.team import TeamService


class _Result:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar(self):
        return self.value


class _DB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, Team) and value.id is None:
                value.id = uuid.uuid4()
                value.created_at = datetime.now(UTC)
                value.updated_at = datetime.now(UTC)
            if isinstance(value, TeamMember) and value.joined_at is None:
                value.joined_at = datetime.now(UTC)

    async def delete(self, _value):
        return None


def _agent(agent_id: uuid.UUID) -> Agent:
    return Agent(id=agent_id, status="active")


def _member_rows(team_id: uuid.UUID, owner_id: uuid.UUID, member_id: uuid.UUID):
    return _Result(
        rows=[
            TeamMember(team_id=team_id, agent_id=owner_id, role="owner", joined_at=datetime.now(UTC)),
            TeamMember(team_id=team_id, agent_id=member_id, role="member", joined_at=datetime.now(UTC)),
        ]
    )


@pytest.mark.asyncio
async def test_create_team_registers_owner_and_active_members(monkeypatch):
    owner_id, member_id = uuid.uuid4(), uuid.uuid4()
    events = []
    async def publish(event_type, payload):
        events.append((event_type, payload))
    monkeypatch.setattr("app.services.team.service.publish_event", publish)

    db = _DB(_Result(None), _Result(rows=[member_id]), _member_rows(uuid.uuid4(), owner_id, member_id))
    result = await TeamService().create_team(
        db, str(owner_id), "research-team", "Research agents", [str(member_id)]
    )

    team = next(value for value in db.added if isinstance(value, Team))
    members = [value for value in db.added if isinstance(value, TeamMember)]
    assert result["name"] == "research-team"
    assert {member.agent_id for member in members} == {owner_id, member_id}
    assert next(member for member in members if member.agent_id == owner_id).role == "owner"
    assert events[0][0] == "team.created"
    assert team.owner_agent_id == owner_id


@pytest.mark.asyncio
async def test_create_team_rejects_inactive_member():
    owner_id, member_id = uuid.uuid4(), uuid.uuid4()
    db = _DB(_Result(None), _Result(rows=[]))
    with pytest.raises(ValueError, match="active registered agents"):
        await TeamService().create_team(db, str(owner_id), "team", None, [str(member_id)])


@pytest.mark.asyncio
async def test_only_owner_can_add_member_and_duplicate_is_rejected(monkeypatch):
    owner_id, member_id, outsider_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    team = Team(id=uuid.uuid4(), name="team", owner_agent_id=owner_id, status="active")
    active = _Result(_agent(member_id))
    monkeypatch.setattr("app.services.team.service.publish_event", lambda *_args: _noop())

    with pytest.raises(PermissionError, match="team owner"):
        await TeamService().add_member(
            _DB(_Result(team)), str(team.id), str(outsider_id), str(member_id)
        )

    db = _DB(_Result(team), active, _Result(None), _Result(rows=[]))
    result = await TeamService().add_member(db, str(team.id), str(owner_id), str(member_id))
    assert result["id"] == str(team.id)

    duplicate_db = _DB(_Result(team), active, _Result(TeamMember(team_id=team.id, agent_id=member_id)))
    with pytest.raises(ValueError, match="already a team member"):
        await TeamService().add_member(duplicate_db, str(team.id), str(owner_id), str(member_id))


def _noop():
    async def noop():
        return None
    return noop()
