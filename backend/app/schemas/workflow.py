from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkflowTaskDefinition(BaseModel):
    id: str
    agent_capability: str
    depends_on: list[str] = []
    payload: Optional[dict[str, Any]] = None
    constraints: dict[str, Any] = {}


class WorkflowDefinition(BaseModel):
    tasks: list[WorkflowTaskDefinition]


class WorkflowCreateRequest(BaseModel):
    name: str
    definition: WorkflowDefinition
    context: dict[str, Any] = {}


class WorkflowTaskResponse(BaseModel):
    id: str
    node_id: str
    capability_name: str
    depends_on: list[str]
    status: str
    result: Optional[dict[str, Any]] = None


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    status: str
    definition: dict[str, Any]
    context: dict[str, Any] = {}
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    tasks: list[WorkflowTaskResponse] = []
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[WorkflowResponse]
