from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskPrivacyProofCreateRequest(BaseModel):
    outcome: int = Field(ge=0, le=1)
    nonce: str = Field(min_length=32, max_length=512)


class TaskPrivacyProofResponse(BaseModel):
    task_id: str
    scheme: str
    commitment: str
    proof: dict[str, Any]
    created_at: str


class TaskPrivacyProofVerificationResponse(BaseModel):
    task_id: str
    valid: bool
    scheme: str
