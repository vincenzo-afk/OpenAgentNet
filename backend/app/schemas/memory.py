from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryPermissionSchema(BaseModel):
    grantee_agent_id: str
    permission: str = Field(..., pattern="^(read|read_write)$")


class MemoryWriteRequest(BaseModel):
    namespace: str
    key: str
    data: dict[str, Any]
    data_type: str = "json"
    permissions: list[MemoryPermissionSchema] = []
    ephemeral: bool = False
    ttl_seconds: int | None = None


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


class MemoryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MemoryObjectResponse]
