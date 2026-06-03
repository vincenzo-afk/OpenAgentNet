from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskEnvelope(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: str | None = None
    conversation_id: str | None = None
    to: str
    task: str
    payload: dict[str, Any]
    constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    signature: str | None = None


class TaskResponseSchema(BaseModel):
    message_id: str
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    execution_ms: int | None = None
    timestamp: datetime


class MessageEnvelope(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: str
    conversation_id: str | None = None
    from_did: str = Field(alias="from")
    to: str
    type: str
    task: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    reply_to: str | None = None
    timestamp: datetime
    signature: str | None = None

    class Config:
        populate_by_name = True


class SendMessageRequest(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: str | None = None
    conversation_id: str | None = None
    to: str
    type: str = "task.request"
    task: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    constraints: dict[str, Any] = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    signature: str | None = None


class SendMessageResponse(BaseModel):
    message_id: str
    status: str = "queued"
    delivery_mode: str = "http"


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str | None = None
    from_agent_id: str
    to_agent_id: str
    type: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    delivered_at: datetime | None = None

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
    initiator_id: str
    executor_id: str
    capability_slug: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TaskResponse]
