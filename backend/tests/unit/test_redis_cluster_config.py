from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import database


@pytest.mark.asyncio
async def test_get_redis_uses_cluster_startup_nodes(monkeypatch):
    created = {}

    class FakeCluster:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def close(self):
            return None

    monkeypatch.setattr(database, "RedisCluster", FakeCluster)
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(redis_cluster_urls="redis://redis-a:6379,redis://redis-b:6380", redis_url="redis://unused"),
    )
    database._redis_client = None
    client = await database.get_redis()
    assert isinstance(client, FakeCluster)
    assert [(node.host, node.port) for node in created["startup_nodes"]] == [
        ("redis-a", 6379),
        ("redis-b", 6380),
    ]
    assert created["require_full_coverage"] is False
    database._redis_client = None


@pytest.mark.asyncio
async def test_get_redis_rejects_invalid_cluster_startup_url(monkeypatch):
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(redis_cluster_urls="redis://", redis_url="redis://unused"),
    )
    database._redis_client = None
    with pytest.raises(ValueError, match="Invalid Redis Cluster"):
        await database.get_redis()
    database._redis_client = None
