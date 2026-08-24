from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    description: str | None = Field(default=None, max_length=2000)
    member_agent_ids: list[str] = Field(default_factory=list, max_length=100)


class TeamMemberRequest(BaseModel):
    agent_id: str


class TeamMemberResponse(BaseModel):
    agent_id: str
    role: str
    joined_at: datetime


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_agent_id: str
    status: str
    members: list[TeamMemberResponse]
    created_at: datetime
    updated_at: datetime


class TeamListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TeamResponse]
