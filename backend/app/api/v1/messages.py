from __future__ import annotations

import uuid
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task

from app.core.dependencies import get_db_session, require_scope
from app.schemas.task import (
    MessageListResponse,
    SendMessageRequest,
    SendMessageResponse,
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


@router.post("/{message_id}/result", status_code=status.HTTP_200_OK)
async def report_task_result(
    message_id: str,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:send"))],
):
    """Agent-reported task outcome. Closes the trust loop:

    Executors (or initiators) POST the execution result of a previously
    dispatched task. Status must be one of ``success`` / ``partial`` /
    ``failed`` / ``declined``. The trust service records the outcome so the
    agent's trust score reflects real behaviour (PROTOCOL.md section 5).
    """
    from app.core.identifiers import parse_agent_id

    agent_id = payload.get("agent_id", "")
    resolved = parse_agent_id(agent_id)
    if not resolved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent_id")

    try:
        msg_uuid = uuid.UUID(message_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message_id")

    result_data = await db.execute(select(Task).where(Task.id == msg_uuid))
    task = result_data.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if resolved not in (task.from_agent_id, task.to_agent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants may report a task result",
        )

    outcome_status = str(body.get("status", "success"))
    if outcome_status not in ("success", "partial", "failed", "declined"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be success/partial/failed/declined",
        )

    task.status = outcome_status
    task.result = body.get("result") or task.result
    if outcome_status == "failed":
        task.error_code = body.get("error_code", task.error_code)
        task.error_message = body.get("error_message", task.error_message)
    if body.get("execution_ms"):
        task.execution_ms = int(body["execution_ms"])
    task.completed_at = datetime.now(UTC)
    await db.flush()

    # Record the outcome with the trust service (closes the trust loop)
    from app.services.trust import TrustService

    trust_service = TrustService()
    await trust_service.record_outcome(
        db,
        task_id=str(task.id),
        success=outcome_status == "success",
        execution_ms=task.execution_ms,
    )

    return {
        "message_id": message_id,
        "status": task.status,
        "updated_at": task.completed_at.isoformat() if task.completed_at else None,
    }


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
    from datetime import datetime

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
            created_at=datetime.now(UTC),
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
        initiator_id=message["from_agent_id"],
        executor_id=message["to_agent_id"],
        capability_slug=message.get("capability", ""),
        status=message["status"],
        payload=message["payload"],
        started_at=message.get("created_at"),
        completed_at=message.get("delivered_at"),
    )


@task_router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("tasks:read"))],
    role: str | None = None,
    status_filter: str | None = None,
    capability: str | None = None,
    since: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    agent_id = payload.get("agent_id", "")
    direction = "sent" if role == "initiator" else "received" if role == "executor" else None
    result = await messaging_service.list_messages(
        db,
        agent_id=agent_id,
        direction=direction,
        since=since,
        limit=limit,
        offset=offset,
    )
    items = [
        TaskResponse(
            task_id=m["message_id"],
            initiator_id=m["from_agent_id"],
            executor_id=m["to_agent_id"],
            capability_slug=m.get("capability", ""),
            status=m["status"],
            payload=m["payload"],
            started_at=m.get("created_at"),
            completed_at=m.get("delivered_at"),
        )
        for m in result["items"]
        if (not capability or m.get("capability", "") == capability)
        and (not status_filter or m["status"] == status_filter)
    ]
    return TaskListResponse(
        total=len(items),
        limit=limit,
        offset=offset,
        items=items,
    )
