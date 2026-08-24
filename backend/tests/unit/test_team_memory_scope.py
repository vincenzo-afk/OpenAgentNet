from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.memory import MemoryObject, MemoryPermission
from app.services.memory import MemoryService


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
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
            if isinstance(value, MemoryObject) and value.id is None:
                value.id = uuid.uuid4()


@pytest.mark.asyncio
async def test_team_scope_grants_access_to_team(monkeypatch):
    owner_id, team_id = uuid.uuid4(), uuid.uuid4()
    team = SimpleNamespace(id=team_id, owner_agent_id=owner_id, status="active")
    events = []

    async def publish(*args, **kwargs):
        events.append(args[0])
    monkeypatch.setattr("app.services.memory.service.publish_event", publish)

    db = _DB(_Result(team), _Result(None), _Result(None))
    result = await MemoryService().write_memory(
        db,
        str(owner_id),
        "team:shared",
        "brief",
        {"text": "hello"},
        scope="team",
        team_id=str(team_id),
    )

    permission = next(value for value in db.added if isinstance(value, MemoryPermission))
    assert permission.team_id == team_id
    assert permission.grantee_agent_id is None
    assert result["key"] == "brief"
    assert events == ["memory.created", "memory.updated"]


@pytest.mark.asyncio
async def test_team_member_can_read_team_granted_memory():
    owner_id, member_id, team_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    memory = SimpleNamespace(
        id=uuid.uuid4(), owner_agent_id=owner_id, namespace="team:shared", key="brief",
        data={"text": "hello"}, data_type="json", is_ephemeral=False,
        version=1, created_at=None, updated_at=None, expires_at=None, embedding=None,
    )
    db = _DB(_Result(memory), _Result(None), _Result(SimpleNamespace(id=uuid.uuid4())))
    result = await MemoryService().read_memory(db, str(member_id), str(memory.id))
    assert result["id"] == str(memory.id)


@pytest.mark.asyncio
async def test_team_scope_requires_owner():
    owner_id, team_id = uuid.uuid4(), uuid.uuid4()
    team = SimpleNamespace(id=team_id, owner_agent_id=uuid.uuid4(), status="active")
    with pytest.raises(ValueError, match="team owner"):
        await MemoryService().write_memory(
            _DB(_Result(team)), str(owner_id), "team:shared", "brief", {},
            scope="team", team_id=str(team_id),
        )
