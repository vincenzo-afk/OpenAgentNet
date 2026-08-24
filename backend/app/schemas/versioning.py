from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentVersionResponse(BaseModel):
    agent_id: str
    revision: int
    version: str
    endpoint: str
    capabilities: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime


class AgentVersionListResponse(BaseModel):
    agent_id: str
    total: int
    items: list[AgentVersionResponse]


class CapabilityChange(BaseModel):
    name: str
    change: str = Field(pattern=r"^(added|removed|changed)$")
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class AgentVersionDiffResponse(BaseModel):
    agent_id: str
    from_revision: int
    to_revision: int
    version_changed: bool
    endpoint_changed: bool
    metadata_changed: bool
    capabilities: list[CapabilityChange]
