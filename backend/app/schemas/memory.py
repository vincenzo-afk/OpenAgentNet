from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryPermissionSchema(BaseModel):
    grantee_agent_id: str | None = None
    team_id: str | None = None
    permission: str = Field(..., pattern="^(read|read_write)$")


class MemoryWriteRequest(BaseModel):
    namespace: str
    key: str
    data: dict[str, Any]
    data_type: str = "json"
    permissions: list[MemoryPermissionSchema] = []
    scope: Literal["private", "shared_with", "team"] = "private"
    team_id: str | None = None
    ephemeral: bool = False
    ttl_seconds: int | None = None
    embedding: list[float] | None = None


class MemoryObjectResponse(BaseModel):
    id: str
    namespace: str
    key: str
    owner_agent_id: str
    data: dict[str, Any]
    data_type: str
    is_ephemeral: bool
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemorySearchRequest(BaseModel):
    embedding: list[float] = Field(..., min_length=1)
    namespace: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class MemorySearchResult(MemoryObjectResponse):
    similarity: float


class MemorySearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MemorySearchResult]


class MemoryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MemoryObjectResponse]
