from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiscoverySearchRequest(BaseModel):
    capabilities: list[str] | None = None
    filters: dict[str, Any] = {}
    sort: str = "trust_score:desc"
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class DiscoveryAgentResult(BaseModel):
    agent_id: str
    name: str
    display_name: str | None = None
    version: str
    capabilities: list[str]
    tags: list[str] = []
    trust_score: float | None = None
    metadata: dict[str, Any] = {}
    status: str


class DiscoverySearchResponse(BaseModel):
    total: int
    agents: list[DiscoveryAgentResult]
    query_id: str | None = None
