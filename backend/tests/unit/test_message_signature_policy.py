from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.messaging import MessagingService


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


@pytest.mark.asyncio
async def test_required_signature_rejects_unsigned_message(monkeypatch):
    sender_id, recipient_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        "app.services.messaging.service.get_settings",
        lambda: SimpleNamespace(require_message_signatures=True, validate_task_payloads=False),
    )
    db = _DB(
        _Result(None),
        _Result(SimpleNamespace(id=recipient_id)),
        _Result(SimpleNamespace(id=sender_id)),
    )
    with pytest.raises(ValueError, match="signature is required"):
        await MessagingService().send_message(
            db,
            {"message_id": str(uuid.uuid4()), "to": str(recipient_id), "task": "summarize"},
            str(sender_id),
        )
    assert db.added == []
