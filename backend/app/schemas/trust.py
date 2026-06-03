from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TrustScoreResponse(BaseModel):
    agent_id: str
    score: float
    components: dict[str, float]
    total_tasks: int
    successful_tasks: int
    dispute_count: int
    last_active: datetime | None = None
    computed_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TrustEvent(BaseModel):
    event_id: str | None = None
    event_type: str
    score_delta: float | None = None
    new_score: float | None = None
    reference_id: str | None = None
    timestamp: datetime


class TrustEventsResponse(BaseModel):
    events: list[TrustEvent]


class EndorsementRequest(BaseModel):
    to_agent_id: str
    capability: str
    comment: str | None = None


class EndorsementResponse(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    capability: str
    comment: str | None = None
    weight: float
    created_at: datetime


class DisputeRequest(BaseModel):
    reported_agent_id: str
    reason: str
    task_id: str | None = None
    evidence: dict[str, Any] = {}


class DisputeResponse(BaseModel):
    id: str
    reported_agent_id: str
    reporter_agent_id: str
    reason: str
    status: str
    created_at: datetime
