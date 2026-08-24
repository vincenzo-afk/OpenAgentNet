from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.common import readiness_check


class _DB:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def execute(self, _statement):
        if self.fail:
            raise RuntimeError("database unavailable")
        return None


class _Redis:
    async def ping(self):
        return True


@pytest.mark.asyncio
async def test_readiness_reports_dependency_status(monkeypatch):
    monkeypatch.setattr("app.core.database.get_redis", lambda: _redis())
    monkeypatch.setattr("app.core.nats_client.is_nats_available", lambda: True)
    result = await readiness_check(_DB())
    assert result["status"] == "ready"
    assert result["checks"] == {"database": "ok", "redis": "ok", "nats": "ok"}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.core.database.get_redis", lambda: _redis())
    response = await readiness_check(_DB(fail=True))
    assert response.status_code == 503


def _redis():
    async def resolve():
        return _Redis()
    return resolve()
