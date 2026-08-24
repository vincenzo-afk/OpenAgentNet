from __future__ import annotations

import uuid

import pytest

from app.core import capability_index


class _Redis:
    def __init__(self):
        self.sets: dict[str, set[str]] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.deleted: list[str] = []

    async def smembers(self, key):
        return self.sets.get(key, set())

    async def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    async def delete(self, key):
        self.deleted.append(key)
        self.sets.pop(key, None)

    async def zadd(self, key, values):
        self.sorted_sets.setdefault(key, {}).update(values)

    async def zrem(self, key, value):
        self.sorted_sets.setdefault(key, {}).pop(value, None)

    async def zrangebyscore(self, key, minimum, _maximum):
        values = self.sorted_sets.get(key, {})
        minimum = float("-inf") if minimum == "-inf" else float(minimum)
        return [agent_id for agent_id, score in values.items() if score >= minimum]


@pytest.mark.asyncio
async def test_sync_and_candidate_intersection(monkeypatch) -> None:
    redis = _Redis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(capability_index, "get_redis", fake_get_redis)
    first = uuid.uuid4()
    second = uuid.uuid4()
    await capability_index.sync_agent(first, [{"name": "summarize"}, {"name": "translate"}], trust_score=0.9)
    await capability_index.sync_agent(second, [{"name": "summarize"}], trust_score=0.8)

    result = await capability_index.candidate_ids(["summarize", "translate"], min_trust_score=0.85)
    assert result == [first]


@pytest.mark.asyncio
async def test_update_and_remove_agent_index(monkeypatch) -> None:
    redis = _Redis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(capability_index, "get_redis", fake_get_redis)
    agent_id = uuid.uuid4()
    await capability_index.sync_agent(agent_id, [{"name": "summarize"}], trust_score=0.5)
    await capability_index.update_agent_score(agent_id, 0.95)
    assert redis.sorted_sets["oan:capability:summarize"][str(agent_id)] == 0.95
    await capability_index.remove_agent(agent_id)
    assert str(agent_id) not in redis.sorted_sets["oan:capability:summarize"]
