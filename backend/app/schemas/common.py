from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Any]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class AuditEventResponse(BaseModel):
    id: int
    event_type: str
    actor_id: str | None = None
    target_id: str | None = None
    target_type: str | None = None
    payload: dict = {}
    ip_address: str | None = None
    occurred_at: str


class AuditListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditEventResponse]


class SuspendRequest(BaseModel):
    reason: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    api_token: str
    expires_at: str
