from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


_REGION = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")


class RegistryPeerCreate(BaseModel):
    registry_id: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    endpoint: HttpUrl
    region: str = _REGION
    metadata: dict[str, Any] = {}


class RegistryPeerResponse(BaseModel):
    registry_id: str
    name: str
    endpoint: str
    region: str
    is_active: bool
    last_sync_at: datetime | None = None
    last_sync_cursor: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime | None = None


class RegistryPeerCreatedResponse(RegistryPeerResponse):
    shared_secret: str


class FederatedAgentRecord(BaseModel):
    agent_id: str
    did: str
    name: str = Field(min_length=2, max_length=100)
    display_name: str | None = None
    version: str
    description: str | None = None
    status: str = "active"
    region: str = _REGION
    endpoint: HttpUrl
    health_endpoint: HttpUrl | None = None
    public_key: str
    capabilities: list[dict[str, Any]] = []
    permissions_required: list[str] = []
    permissions_offered: list[str] = []
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    updated_at: datetime | None = None


class RegistrySyncRequest(BaseModel):
    source_registry_id: str = Field(min_length=2, max_length=128)
    cursor: str | None = Field(default=None, max_length=256)
    agents: list[FederatedAgentRecord] = Field(default_factory=list, max_length=1000)
    removed_agent_ids: list[str] = Field(default_factory=list, max_length=1000)


class RegistrySyncResponse(BaseModel):
    source_registry_id: str
    accepted: int
    removed: int
    rejected: int
    next_cursor: str
    synced_at: datetime


class AgentMigrationRequest(BaseModel):
    target_region: str = _REGION
    target_registry_id: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")
    reason: str | None = Field(default=None, max_length=500)


class AgentMigrationResponse(BaseModel):
    agent_id: str
    previous_region: str
    region: str
    previous_registry_id: str | None
    origin_registry_id: str | None
    migrated_at: datetime
