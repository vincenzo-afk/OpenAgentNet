from __future__ import annotations

import logging
from typing import Any

from app.core.database import get_redis

logger = logging.getLogger(__name__)

FLAG_TTL_SECONDS = 15 * 60
DEFAULT_WINDOW_SECONDS = 5 * 60


async def observe_anomaly(
    subject_id: str,
    anomaly_type: str,
    *,
    threshold: int,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> bool:
    """Record an anomaly signal and flag the subject after the threshold.

    Redis is deliberately treated as an optional protection layer. If it is
    unavailable, the request or task flow remains available and the event is
    logged for operators instead of failing closed on infrastructure health.
    """
    if not subject_id or threshold <= 0:
        return False
    try:
        redis = await get_redis()
        key = f"oan:anomaly:{anomaly_type}:{subject_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count >= threshold:
            flag_key = f"oan:anomaly:flag:{subject_id}"
            await redis.set(flag_key, anomaly_type, ex=FLAG_TTL_SECONDS)
            return True
    except Exception:
        logger.warning("Unable to record %s anomaly for %s", anomaly_type, subject_id, exc_info=True)
    return False


async def is_anomaly_flagged(subject_id: str) -> bool:
    if not subject_id:
        return False
    try:
        redis = await get_redis()
        return bool(await redis.get(f"oan:anomaly:flag:{subject_id}"))
    except Exception:
        logger.warning("Unable to read anomaly flag for %s", subject_id, exc_info=True)
        return False
