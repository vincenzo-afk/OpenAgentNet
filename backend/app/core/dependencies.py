from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db, get_redis
from app.core.security import decode_token, is_token_revoked

security = HTTPBearer()


async def get_current_subject(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
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


def require_scope(required_scope: str):
    async def _check(
        payload: Annotated[dict, Depends(get_current_subject)],
    ) -> dict:
        scopes = payload.get("scopes", [])
        if required_scope not in scopes and "admin" not in scopes:
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
