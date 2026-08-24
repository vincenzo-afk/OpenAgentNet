from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RoutingRequest(BaseModel):
    task_description: str = Field(min_length=1, max_length=4000)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    constraints: dict[str, Any] = {}
    limit: int = Field(default=5, ge=1, le=20)


class RoutingCandidate(BaseModel):
    agent_id: str
    did: str
    name: str
    region: str
    trust_score: float
    capability_match: float
    score: float
    reasons: list[str] = []


class RoutingResponse(BaseModel):
    selected_agent_id: str | None = None
    selected_did: str | None = None
    strategy: str
    candidates: list[RoutingCandidate]
    rationale: str
