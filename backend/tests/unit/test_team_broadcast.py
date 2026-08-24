from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.task import Task
from app.services.messaging import MessagingService


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


class _DB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.committed = False

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True


class _HTTPClient:
    def __init__(self):
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, endpoint, **_kwargs):
        self.posts.append(endpoint)
        return SimpleNamespace(status_code=202)


@pytest.mark.asyncio
async def test_team_broadcast_persists_and_delivers_to_each_active_member(monkeypatch):
    sender_id = uuid.uuid4()
    team_id = uuid.uuid4()
    members = [
        SimpleNamespace(id=uuid.uuid4(), endpoint="https://one.example/task"),
        SimpleNamespace(id=uuid.uuid4(), endpoint="https://two.example/task"),
    ]
    sender = SimpleNamespace(id=sender_id, public_key="unused")
    client = _HTTPClient()
    events = []

    async def audit(*_args, **_kwargs):
        events.append("audit")

    async def publish_team(*_args, **_kwargs):
        events.append("nats")
        return True

    monkeypatch.setattr("app.services.messaging.service.log_audit_event", audit)
    monkeypatch.setattr("app.services.messaging.service.publish_to_team", publish_team)
    monkeypatch.setattr("app.services.messaging.service.httpx.AsyncClient", lambda **_kwargs: client)

    db = _DB(_Result(sender), _Result(SimpleNamespace(id=team_id, status="active")), _Result(rows=members))
    result = await MessagingService().send_message(
        db,
        {
            "to": f"team:{team_id}",
            "type": "task.request",
            "task": {"name": "summarize", "payload": {"text": "hello"}},
            "ttl_seconds": 60,
        },
        str(sender_id),
    )

    tasks = [value for value in db.added if isinstance(value, Task)]
    assert result["delivery_mode"] == "team-nats"
    assert result["member_count"] == 2
    assert result["http_delivered"] == 2
    assert len(result["task_ids"]) == 2
    assert {task.to_agent_id for task in tasks} == {member.id for member in members}
    assert client.posts == [member.endpoint for member in members]
    assert db.committed is True
    assert events == ["audit", "nats"]


@pytest.mark.asyncio
async def test_team_destination_dispatches_before_direct_recipient_logic(monkeypatch):
    expected = {"message_id": str(uuid.uuid4()), "status": "queued", "delivery_mode": "team-http"}
    calls = []

    async def broadcast(_self, _db, envelope, sender_id):
        calls.append((envelope["to"], sender_id))
        return expected

    monkeypatch.setattr(MessagingService, "broadcast_to_team", broadcast)
    result = await MessagingService().send_message(
        None, {"to": "team:" + str(uuid.uuid4())}, str(uuid.uuid4())
    )
    assert result == expected
    assert calls
