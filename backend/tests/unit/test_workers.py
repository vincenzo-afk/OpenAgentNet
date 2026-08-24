from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core import workers


@pytest.mark.asyncio
async def test_record_terminal_outcome_delegates_to_trust_service(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeTrustService:
        async def record_outcome(self, db, task_id, success, execution_ms):
            calls.update(
                db=db,
                task_id=task_id,
                success=success,
                execution_ms=execution_ms,
            )

    monkeypatch.setattr(workers, "TrustService", FakeTrustService)
    task_id = uuid.uuid4()
    task = SimpleNamespace(id=task_id, execution_ms=900)

    await workers._record_terminal_outcome("db", task)

    assert calls == {
        "db": "db",
        "task_id": str(task_id),
        "success": False,
        "execution_ms": 900,
    }
