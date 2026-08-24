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
        lambda: SimpleNamespace(
            redis_cluster_urls="rediss://cluster-user:cluster%2Fpassword@redis-a:6379,rediss://redis-b:6380",
            redis_url="redis://unused",
        ),
    )
    database._redis_client = None
    client = await database.get_redis()
    assert isinstance(client, FakeCluster)
    assert [(node.host, node.port) for node in created["startup_nodes"]] == [
        ("redis-a", 6379),
        ("redis-b", 6380),
    ]
    assert created["require_full_coverage"] is False
    assert created["ssl"] is True
    assert created["username"] == "cluster-user"
    assert created["password"] == "cluster/password"
    database._redis_client = None


@pytest.mark.asyncio
async def test_get_redis_uses_single_node_fallback(monkeypatch):
    calls = []

    class FakeRedis:
        pass

    def fake_from_url(url, **kwargs):
        calls.append((url, kwargs))
        return FakeRedis()

    monkeypatch.setattr(database.Redis, "from_url", fake_from_url)
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(redis_cluster_urls="", redis_url="redis://redis:6379/0"),
    )
    database._redis_client = None
    client = await database.get_redis()
    assert isinstance(client, FakeRedis)
    assert calls == [("redis://redis:6379/0", {"decode_responses": True})]
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
