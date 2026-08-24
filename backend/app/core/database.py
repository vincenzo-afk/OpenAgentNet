from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster
from redis.cluster import ClusterNode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine = None
_session_factory = None
_redis_client: Redis | RedisCluster | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> Redis | RedisCluster:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        cluster_urls = [url.strip() for url in settings.redis_cluster_urls.split(",") if url.strip()]
        if cluster_urls:
            nodes = []
            for url in cluster_urls:
                parsed = urlparse(url)
                if not parsed.hostname:
                    raise ValueError("Invalid Redis Cluster startup URL")
                nodes.append(ClusterNode(parsed.hostname, parsed.port or 6379))
            _redis_client = RedisCluster(
                startup_nodes=nodes,
                decode_responses=True,
                require_full_coverage=False,
            )
        else:
            _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_connections():
    global _engine, _redis_client
    if _engine:
        await _engine.dispose()
        _engine = None
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
