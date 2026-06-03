from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskEnvelope(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    to: str
    task: str
    payload: dict[str, Any]
    constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    signature: Optional[str] = None


class TaskResponseSchema(BaseModel):
    message_id: str
    task_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    execution_ms: Optional[int] = None
    timestamp: datetime


class MessageEnvelope(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: str
    conversation_id: Optional[str] = None
    from_did: str = Field(alias="from")
    to: str
    type: str
    task: Optional[dict[str, Any]] = None
    body: Optional[dict[str, Any]] = None
    reply_to: Optional[str] = None
    timestamp: datetime
    signature: Optional[str] = None

    class Config:
        populate_by_name = True


class SendMessageRequest(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    to: str
    type: str = "task.request"
    task: Optional[dict[str, Any]] = None
    body: Optional[dict[str, Any]] = None
    payload: Optional[dict[str, Any]] = None
    constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    signature: Optional[str] = None


class SendMessageResponse(BaseModel):
    message_id: str
    status: str = "queued"
    delivery_mode: str = "http"


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: Optional[str] = None
    from_agent_id: str
    to_agent_id: str
    type: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MessageResponse]


class TaskCreateRequest(BaseModel):
    executor_id: str
    capability_slug: str
    payload: dict[str, Any]
    constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str = "pending"
    created_at: datetime


class TaskResponse(BaseModel):
    task_id: str
    from_agent_id: str
    to_agent_id: str
    capability_name: str
    status: str
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    execution_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TaskResponse]
