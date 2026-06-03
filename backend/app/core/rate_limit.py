from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import get_redis

# Endpoint -> (limit, window_seconds)
RATE_LIMIT_MAP: dict[str, tuple[int, int]] = {
    "/v1/agents/register": (10, 3600),  # 10/hour
    "/v1/discover": (200, 60),  # 200/min
    "/v1/discovery/search": (200, 60),  # 200/min
    "/v1/messages": (1000, 60),  # 1000/min
    "/v1/trust": (50, 3600),  # 50/hour (endorse)
}


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """Enforce max_payload_bytes on request bodies (SECURITY.md requirement)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_payload_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request payload too large"},
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for docs and health
        if request.url.path in ("/docs", "/redoc", "/openapi.json", "/health", "/v1/health", "/"):
            return await call_next(request)

        # Get client identifier (agent_id from token or IP)
        client_id = self._get_client_id(request)
        if not client_id:
            return await call_next(request)

        # Find matching rate limit
        rate_limit = self._get_rate_limit(request.url.path)
        if rate_limit is None:
            return await call_next(request)
        limit, window = rate_limit

        # Check rate limit in Redis
        try:
            redis = await get_redis()
            key = f"ratelimit:{client_id}:{request.url.path}"
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window)

            if current > limit:
                retry_after = await redis.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                        "Retry-After": str(retry_after),
                    },
                )

            response = await call_next(request)
            remaining = max(0, limit - current)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
            return response

        except Exception:
            # If Redis is unavailable, allow the request
            return await call_next(request)

    def _get_client_id(self, request: Request) -> str | None:
        # Try to get agent_id from Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from app.core.security import decode_token

            token = auth[7:]
            payload = decode_token(token)
            if payload:
                return payload.get("agent_id", payload.get("sub", ""))
        # Fall back to IP
        return request.client.host if request.client else None

    def _get_rate_limit(self, path: str) -> tuple[int, int] | None:
        for pattern, limits in RATE_LIMIT_MAP.items():
            if path.startswith(pattern):
                return limits
        return None
