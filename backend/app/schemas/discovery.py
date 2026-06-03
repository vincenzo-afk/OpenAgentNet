from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DiscoverySearchRequest(BaseModel):
    capabilities: Optional[list[str]] = None
    filters: dict[str, Any] = {}
    sort: str = "trust_score:desc"
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class DiscoveryAgentResult(BaseModel):
    agent_id: str
    name: str
    display_name: Optional[str] = None
    version: str
    capabilities: list[str]
    tags: list[str] = []
    trust_score: Optional[float] = None
    metadata: dict[str, Any] = {}
    status: str


class DiscoverySearchResponse(BaseModel):
    total: int
    agents: list[DiscoveryAgentResult]
    query_id: Optional[str] = None
