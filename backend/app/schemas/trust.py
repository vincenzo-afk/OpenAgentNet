from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TrustScoreResponse(BaseModel):
    agent_id: str
    score: float
    components: dict[str, float]
    total_tasks: int
    successful_tasks: int
    dispute_count: int
    last_active: Optional[datetime] = None
    computed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrustEvent(BaseModel):
    event_id: Optional[str] = None
    event_type: str
    score_delta: Optional[float] = None
    new_score: Optional[float] = None
    reference_id: Optional[str] = None
    timestamp: datetime


class TrustEventsResponse(BaseModel):
    events: list[TrustEvent]


class EndorsementRequest(BaseModel):
    to_agent_id: str
    capability: str
    comment: Optional[str] = None


class EndorsementResponse(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    capability: str
    comment: Optional[str] = None
    weight: float
    created_at: datetime


class DisputeRequest(BaseModel):
    reported_agent_id: str
    reason: str
    task_id: Optional[str] = None
    evidence: dict[str, Any] = {}


class DisputeResponse(BaseModel):
    id: str
    reported_agent_id: str
    reporter_agent_id: str
    reason: str
    status: str
    created_at: datetime
