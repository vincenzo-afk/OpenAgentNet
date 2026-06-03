from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CapabilitySchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tags: list[str] = []
    latency_estimate_ms: Optional[int] = None
    cost_estimate: Optional[dict[str, Any]] = None


class AgentManifest(BaseModel):
    protocol_version: str = "0.1.0"
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    display_name: Optional[str] = None
    version: str
    description: str
    owner: dict[str, Any]
    capabilities: list[CapabilitySchema]
    endpoint: str
    health_endpoint: Optional[str] = None
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
    display_name: Optional[str] = None
    version: str
    description: Optional[str] = None
    status: str
    endpoint: str
    capabilities: list[CapabilitySchema]
    tags: list[str]
    trust_score: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    version: Optional[str] = None
    endpoint: Optional[str] = None
    health_endpoint: Optional[str] = None
    capabilities: Optional[list[CapabilitySchema]] = None
    permissions_required: Optional[list[str]] = None
    permissions_offered: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class AgentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AgentResponse]
