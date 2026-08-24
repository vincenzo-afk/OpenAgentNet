from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from starlette.responses import Response

from app.core import anomaly, rate_limit
from app.services.trust.service import TrustService


class _FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.flags: dict[str, str] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds

    async def set(self, key: str, value: str, *, ex: int) -> None:
        self.flags[key] = value
        self.expiries[key] = ex

    async def get(self, key: str):
        return self.flags.get(key)


@pytest.mark.asyncio
async def test_anomaly_tracker_flags_subject_at_threshold(monkeypatch) -> None:
    redis = _FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(anomaly, "get_redis", fake_get_redis)
    assert await anomaly.observe_anomaly("agent-1", "schema_violation", threshold=2) is False
    assert await anomaly.observe_anomaly("agent-1", "schema_violation", threshold=2) is True
    assert await anomaly.is_anomaly_flagged("agent-1") is True
    assert redis.expiries["oan:anomaly:flag:agent-1"] == anomaly.FLAG_TTL_SECONDS


@pytest.mark.asyncio
async def test_high_failure_rate_emits_and_flags_anomaly(monkeypatch) -> None:
    emitted: list[tuple[str, dict]] = []
    flagged: list[tuple[str, str]] = []

    async def fake_emit(_db, _agent_id, anomaly_type, payload):
        emitted.append((anomaly_type, payload))

    async def fake_observe(subject_id, anomaly_type, **_kwargs):
        flagged.append((subject_id, anomaly_type))
        return True

    service = TrustService()
    service._emit_anomaly = fake_emit
    monkeypatch.setattr(anomaly, "observe_anomaly", fake_observe)
    record = SimpleNamespace(
        agent_id=uuid.uuid4(),
        total_tasks=5,
        outcome_rate=0.2,
        last_computed_at=None,
    )

    await service._check_anomalies(None, record)

    assert emitted[0][0] == "failure_rate_high"
    assert emitted[0][1]["failure_rate"] == 0.8
    assert flagged == [(str(record.agent_id), "failure_rate")]


@pytest.mark.asyncio
async def test_flagged_subject_receives_reduced_rate_limit(monkeypatch) -> None:
    class Redis:
        async def incr(self, _key):
            return 251

        async def ttl(self, _key):
            return 30

    async def fake_get_redis():
        return Redis()

    async def fake_flagged(_subject_id):
        return True

    async def fake_observe(*_args, **_kwargs):
        return True

    monkeypatch.setattr(rate_limit, "get_redis", fake_get_redis)
    monkeypatch.setattr(rate_limit, "is_anomaly_flagged", fake_flagged)
    monkeypatch.setattr(rate_limit, "observe_anomaly", fake_observe)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/v1/messages"),
        headers={},
        client=SimpleNamespace(host="agent-1"),
    )

    response = await rate_limit.RateLimitMiddleware.__new__(rate_limit.RateLimitMiddleware).dispatch(
        request,
        lambda _request: _response(),
    )

    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "250"


async def _response() -> Response:
    return Response("ok", status_code=200)
