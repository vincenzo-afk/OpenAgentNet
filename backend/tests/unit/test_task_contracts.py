from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.negotiation import Negotiation
from app.models.task import Task
from app.models.task_contract import TaskContract
from app.services.messaging import MessagingService
from app.services.negotiation import NegotiationService


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
        for value in self.added:
            if isinstance(value, TaskContract) and value.id is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_acceptance_creates_contract_snapshot(monkeypatch):
    requester_id, target_id = uuid.uuid4(), uuid.uuid4()
    negotiation = Negotiation(
        id=uuid.uuid4(),
        requester_id=requester_id,
        target_id=target_id,
        capability="summarize",
        status="proposed",
        proposal={"capability": "summarize", "max_cost_usd": 0.05},
        round_count=1,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    async def emit(*_args, **_kwargs):
        return None
    monkeypatch.setattr("app.services.negotiation.service._emit_negotiation_event", emit)

    db = _DB(_Result(rows=[]), _Result(negotiation))
    result = await NegotiationService().respond(
        db,
        str(negotiation.id),
        {"decision": "accepted", "agreed_constraints": {"ttl_seconds": 30}},
        str(target_id),
    )

    contract = next(value for value in db.added if isinstance(value, TaskContract))
    assert result["status"] == "accepted"
    assert result["contract_id"] == str(contract.id)
    assert contract.requester_id == requester_id
    assert contract.target_id == target_id
    assert contract.terms["agreed_constraints"]["ttl_seconds"] == 30
    assert contract.session_token == negotiation.session_token


@pytest.mark.asyncio
async def test_contract_backed_task_is_validated_and_bound(monkeypatch):
    requester_id, target_id = uuid.uuid4(), uuid.uuid4()
    message_id = uuid.uuid4()
    contract = SimpleNamespace(
        id=uuid.uuid4(),
        requester_id=requester_id,
        target_id=target_id,
        capability="summarize",
        status="active",
        negotiation_id=uuid.uuid4(),
    )
    recipient = SimpleNamespace(id=target_id, endpoint="https://target.example/task")
    sender = SimpleNamespace(id=requester_id, public_key="unused")
    db = _DB(_Result(None), _Result(recipient), _Result(sender), _Result(contract))

    async def audit(*_args, **_kwargs):
        return None
    async def publish(*_args, **_kwargs):
        return False
    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def post(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=202)
    monkeypatch.setattr("app.services.messaging.service.log_audit_event", audit)
    monkeypatch.setattr("app.services.messaging.service.publish_to_agent", publish)
    monkeypatch.setattr("app.services.messaging.service.httpx.AsyncClient", lambda **_kwargs: _Client())

    result = await MessagingService().send_message(
        db,
        {
            "message_id": str(message_id),
            "to": str(target_id),
            "task": {"name": "summarize", "payload": {"text": "hello"}},
            "contract_id": str(contract.id),
            "ttl_seconds": 60,
        },
        str(requester_id),
    )

    task = next(value for value in db.added if isinstance(value, Task))
    assert result["message_id"] == str(message_id)
    assert task.contract_id == contract.id
    assert task.negotiation_id == contract.negotiation_id


@pytest.mark.asyncio
async def test_contract_backed_task_rejects_capability_mismatch():
    requester_id, target_id = uuid.uuid4(), uuid.uuid4()
    contract = SimpleNamespace(
        id=uuid.uuid4(), requester_id=requester_id, target_id=target_id,
        capability="translate", status="active", negotiation_id=uuid.uuid4()
    )
    recipient = SimpleNamespace(id=target_id, endpoint="https://target.example/task")
    sender = SimpleNamespace(id=requester_id, public_key="unused")
    db = _DB(_Result(None), _Result(recipient), _Result(sender), _Result(contract))
    with pytest.raises(ValueError, match="does not match"):
        await MessagingService().send_message(
            db,
            {"message_id": str(uuid.uuid4()), "to": str(target_id), "task": {"name": "summarize"}, "contract_id": str(contract.id)},
            str(requester_id),
        )
