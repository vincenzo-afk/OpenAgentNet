from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from urllib.parse import quote

from app.core.database import get_redis

logger = logging.getLogger(__name__)
INDEX_PREFIX = "oan:capability"
AGENT_CAPABILITIES_PREFIX = "oan:agent_capabilities"


def _index_key(capability: str) -> str:
    return f"{INDEX_PREFIX}:{quote(capability, safe='._-')}"


def _agent_capabilities_key(agent_id: uuid.UUID | str) -> str:
    return f"{AGENT_CAPABILITIES_PREFIX}:{agent_id}"


async def sync_agent(
    agent_id: uuid.UUID | str,
    capabilities: Iterable[dict],
    *,
    trust_score: float = 0.5,
    active: bool = True,
) -> None:
    """Synchronize one agent into capability sorted sets.

    Index writes are intentionally best effort; PostgreSQL remains the source
    of truth and discovery falls back to it whenever Redis is unavailable.
    """
    agent_key = _agent_capabilities_key(agent_id)
    names = {
        item.get("name")
        for item in capabilities
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item.get("name")
    }
    try:
        redis = await get_redis()
        previous = set(await redis.smembers(agent_key))
        for removed in previous - names:
            await redis.zrem(_index_key(removed), str(agent_id))
        await redis.delete(agent_key)
        if names:
            await redis.sadd(agent_key, *names)
        for name in names:
            if active:
                await redis.zadd(_index_key(name), {str(agent_id): float(trust_score)})
            else:
                await redis.zrem(_index_key(name), str(agent_id))
    except Exception:
        logger.warning("Unable to synchronize capability index for %s", agent_id, exc_info=True)


async def remove_agent(agent_id: uuid.UUID | str) -> None:
    agent_key = _agent_capabilities_key(agent_id)
    try:
        redis = await get_redis()
        for capability in await redis.smembers(agent_key):
            await redis.zrem(_index_key(capability), str(agent_id))
        await redis.delete(agent_key)
    except Exception:
        logger.warning("Unable to remove %s from capability index", agent_id, exc_info=True)


async def update_agent_score(agent_id: uuid.UUID | str, trust_score: float) -> None:
    agent_key = _agent_capabilities_key(agent_id)
    try:
        redis = await get_redis()
        for capability in await redis.smembers(agent_key):
            await redis.zadd(_index_key(capability), {str(agent_id): float(trust_score)})
    except Exception:
        logger.warning("Unable to update capability index score for %s", agent_id, exc_info=True)


async def candidate_ids(
    capabilities: Iterable[str], *, min_trust_score: float | None = None
) -> list[uuid.UUID] | None:
    """Return indexed candidates, or ``None`` when Redis cannot answer."""
    names = [name for name in capabilities if name]
    if not names:
        return None
    try:
        redis = await get_redis()
        candidate_sets: list[set[str]] = []
        minimum = min_trust_score if min_trust_score is not None else "-inf"
        for name in names:
            values = await redis.zrangebyscore(_index_key(name), minimum, "+inf")
            candidate_sets.append(set(values))
        ids = set.intersection(*candidate_sets) if candidate_sets else set()
        parsed: list[uuid.UUID] = []
        for value in ids:
            try:
                parsed.append(uuid.UUID(value))
            except (ValueError, AttributeError):
                continue
        return parsed
    except Exception:
        logger.warning("Unable to read capability index", exc_info=True)
        return None
