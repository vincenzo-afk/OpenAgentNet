from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NegotiationProposalRequest(BaseModel):
    target_id: str
    capability: str
    proposed_payload_schema: dict[str, Any]
    proposed_constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)


class NegotiationProposalResponse(BaseModel):
    negotiation_id: str
    status: str
    session_token: str | None = None
    expires_at: datetime
    created_at: datetime


class NegotiationRespondRequest(BaseModel):
    decision: str = Field(..., pattern="^(accepted|countered|declined)$")
    agreed_constraints: dict[str, Any] | None = None
    counter_proposal: dict[str, Any] | None = None


class NegotiationResponseSchema(BaseModel):
    negotiation_id: str
    status: str
    session_token: str | None = None
    updated_at: datetime


class NegotiationDetail(BaseModel):
    id: str
    requester_id: str
    target_id: str
    capability: str
    status: str
    proposal: dict[str, Any]
    response: dict[str, Any] | None = None
    session_token: str | None = None
    round_count: int
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True
