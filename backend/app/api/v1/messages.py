from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.task import (
    SendMessageRequest,
    SendMessageResponse,
    MessageListResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskResponse,
)
from app.services.messaging import MessagingService

router = APIRouter(prefix="/messages", tags=["messages"])
messaging_service = MessagingService()


@router.post("", response_model=SendMessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    body: SendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:send"))],
):
    try:
        agent_id = payload.get("agent_id", "")
        envelope = body.model_dump()
        result = await messaging_service.send_message(db, envelope, agent_id)
        return SendMessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{message_id}")
async def get_message(
    message_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:read"))],
):
    agent_id = payload.get("agent_id", "")
    message = await messaging_service.get_message(db, message_id, agent_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


@router.get("", response_model=MessageListResponse)
async def list_messages(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:read"))],
    direction: str | None = None,
    type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    agent_id = payload.get("agent_id", "")
    result = await messaging_service.list_messages(
        db,
        agent_id=agent_id,
        direction=direction,
        message_type=type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return MessageListResponse(**result)


task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@task_router.post("", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("tasks:initiate"))],
):
    import uuid
    from datetime import datetime, timezone

    agent_id = payload.get("agent_id", "")
    envelope = {
        "to": f"did:oan:{body.executor_id}",
        "task": body.capability_slug,
        "payload": body.payload,
        "constraints": body.constraints,
        "ttl_seconds": body.ttl_seconds,
    }
    try:
        result = await messaging_service.send_message(db, envelope, agent_id)
        return TaskCreateResponse(
            task_id=result["message_id"],
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@task_router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("tasks:read"))],
):
    agent_id = payload.get("agent_id", "")
    message = await messaging_service.get_message(db, task_id, agent_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse(
        task_id=message["message_id"],
        from_agent_id=message["from_agent_id"],
        to_agent_id=message["to_agent_id"],
        capability_name="",
        status=message["status"],
        payload=message["payload"],
        created_at=message["created_at"],
    )


@task_router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("tasks:read"))],
    role: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    agent_id = payload.get("agent_id", "")
    direction = "sent" if role == "initiator" else "received" if role == "executor" else None
    result = await messaging_service.list_messages(
        db,
        agent_id=agent_id,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    items = [
        TaskResponse(
            task_id=m["message_id"],
            from_agent_id=m["from_agent_id"],
            to_agent_id=m["to_agent_id"],
            capability_name="",
            status=m["status"],
            payload=m["payload"],
            created_at=m["created_at"],
        )
        for m in result["items"]
    ]
    return TaskListResponse(
        total=result["total"],
        limit=limit,
        offset=offset,
        items=items,
    )
