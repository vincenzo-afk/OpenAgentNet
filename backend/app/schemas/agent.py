from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CapabilitySchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tags: list[str] = []
    latency_estimate_ms: int | None = None
    cost_estimate: dict[str, Any] | None = None


class AgentManifest(BaseModel):
    protocol_version: str = "0.1.0"
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    display_name: str | None = None
    version: str
    description: str
    owner: dict[str, Any]
    capabilities: list[CapabilitySchema]
    endpoint: str
    health_endpoint: str | None = None
    public_key: str
    permissions_required: list[str] = []
    permissions_offered: list[str] = []
    tags: list[str] = []
    metadata: dict[str, Any] = {}


class RegistrationProof(BaseModel):
    timestamp: str
    signature: str


class RegistrationRequest(BaseModel):
    identity: AgentManifest
    proof: RegistrationProof


class RegistrationResponse(BaseModel):
    agent_id: str
    did: str
    api_token: str
    registered_at: datetime
    status: str


class AgentResponse(BaseModel):
    agent_id: str
    did: str
    name: str
    display_name: str | None = None
    version: str
    description: str | None = None
    status: str
    endpoint: str
    capabilities: list[CapabilitySchema]
    tags: list[str]
    trust_score: float | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    version: str | None = None
    endpoint: str | None = None
    health_endpoint: str | None = None
    capabilities: list[CapabilitySchema] | None = None
    permissions_required: list[str] | None = None
    permissions_offered: list[str] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class AgentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AgentResponse]
