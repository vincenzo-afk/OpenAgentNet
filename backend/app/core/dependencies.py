from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db, get_redis
from app.core.security import decode_token, is_token_revoked

security = HTTPBearer()


async def get_current_subject(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    """Require a valid JWT. Raises 401 on missing/invalid/revoked tokens."""

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    # Check if token is revoked
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    return payload


async def get_optional_subject(request: Request) -> dict | None:
    """Read the JWT if present (e.g. ``Authorization: Bearer <token>``);

    returns ``None`` for anonymous callers. Used by routes that are
    publicly readable but enrich the response for authenticated agents
    (e.g. public marketplace search, trust-score lookups).
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        return None
    return payload


def require_scope(required_scope: str):
    async def _check(
        payload: Annotated[dict, Depends(get_current_subject)],
    ) -> dict:
        scopes = payload.get("scopes", [])
        if (
            required_scope not in scopes
            and "admin" not in scopes
            # Tokens issued at registration carry "agent:all", which grants all
            # agent-operated scopes (messages:*, tasks:*, discovery:*, memory:*,
            # marketplace:*, negotiate:*, workflow:*, agent:*, trust:*).
            and "agent:all" not in scopes
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}",
            )
        return payload

    return _check


async def get_db_session() -> AsyncGenerator:
    async for session in get_db():
        yield session


async def get_redis_client():
    return await get_redis()
