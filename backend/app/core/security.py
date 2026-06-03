from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings


def create_access_token(
    subject: str,
    scopes: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "access",
    }
    if scopes:
        payload["scopes"] = scopes
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


async def revoke_token(jti: str, exp: datetime) -> None:
    """Add token JTI to Redis denylist until expiry."""
    try:
        from app.core.database import get_redis

        redis = await get_redis()
        ttl = max(int((exp - datetime.now(timezone.utc)).total_seconds()), 1)
        await redis.setex(f"token_denylist:{jti}", ttl, "1")
    except Exception:
        pass


async def is_token_revoked(jti: str) -> bool:
    """Check if token JTI is in Redis denylist."""
    try:
        from app.core.database import get_redis

        redis = await get_redis()
        return await redis.exists(f"token_denylist:{jti}") > 0
    except Exception:
        return False
