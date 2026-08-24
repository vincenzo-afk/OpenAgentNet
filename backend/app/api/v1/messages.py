from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task

from app.core.database import get_session_factory
from app.core.dependencies import get_db_session, require_scope
from app.models.task_stream import TaskStreamChunk
from app.schemas.task import (
    MessageListResponse,
    SendMessageRequest,
    SendMessageResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskResponse,
    TaskStreamChunkRequest,
    TaskStreamChunkResponse,
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
    await db.commit()

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


@task_router.post(
    "/{task_id}/stream",
    response_model=TaskStreamChunkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_task_stream_chunk(
    task_id: str,
    body: TaskStreamChunkRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:send"))],
):
    """Append an ordered incremental result chunk for a task.

    Chunks are idempotent by ``(task_id, sequence)``. Executors may append
    partial results while the task remains running, then mark the final chunk
    with ``is_final`` before reporting the terminal task result.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task_id") from exc

    result = await db.execute(select(Task).where(Task.id == task_uuid))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    actor_id = payload.get("agent_id", "")
    if str(task.to_agent_id) != actor_id and str(task.from_agent_id) != actor_id:
        raise HTTPException(status_code=403, detail="Only participants may append stream chunks")

    existing_result = await db.execute(
        select(TaskStreamChunk).where(
            TaskStreamChunk.task_id == task_uuid,
            TaskStreamChunk.sequence == body.sequence,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        if existing.chunk != body.chunk or existing.is_final != body.is_final:
            raise HTTPException(status_code=409, detail="Stream sequence already contains different data")
        return TaskStreamChunkResponse(
            task_id=str(existing.task_id),
            sequence=existing.sequence,
            chunk=existing.chunk,
            is_final=existing.is_final,
            created_at=existing.created_at,
        )

    if body.sequence > 0:
        previous_result = await db.execute(
            select(TaskStreamChunk).where(
                TaskStreamChunk.task_id == task_uuid,
                TaskStreamChunk.sequence == body.sequence - 1,
            )
        )
        if previous_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Stream sequence must be contiguous")

    chunk = TaskStreamChunk(
        task_id=task_uuid,
        sequence=body.sequence,
        chunk=body.chunk,
        is_final=body.is_final,
    )
    db.add(chunk)
    if task.status in ("pending", "acked"):
        task.status = "running"
    await db.flush()
    return TaskStreamChunkResponse(
        task_id=str(chunk.task_id),
        sequence=chunk.sequence,
        chunk=chunk.chunk,
        is_final=chunk.is_final,
        created_at=chunk.created_at,
    )


@task_router.get("/{task_id}/stream")
async def stream_task_chunks(
    task_id: str,
    payload: Annotated[dict, Depends(require_scope("tasks:read"))],
):
    """Replay existing chunks and stream future chunks as SSE events."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task_id") from exc

    actor_id = payload.get("agent_id", "")
    factory = get_session_factory()
    async with factory() as session:
        task_result = await session.execute(select(Task).where(Task.id == task_uuid))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if str(task.to_agent_id) != actor_id and str(task.from_agent_id) != actor_id:
            raise HTTPException(status_code=403, detail="Only participants may read stream chunks")

    async def events() -> AsyncIterator[str]:
        next_sequence = 0
        deadline = asyncio.get_running_loop().time() + 3600
        while asyncio.get_running_loop().time() < deadline:
            async with factory() as session:
                result = await session.execute(
                    select(TaskStreamChunk)
                    .where(
                        TaskStreamChunk.task_id == task_uuid,
                        TaskStreamChunk.sequence >= next_sequence,
                    )
                    .order_by(TaskStreamChunk.sequence.asc())
                )
                chunks = result.scalars().all()
            for chunk in chunks:
                if chunk.sequence != next_sequence:
                    continue
                payload_data = {
                    "task_id": str(chunk.task_id),
                    "sequence": chunk.sequence,
                    "chunk": chunk.chunk,
                    "is_final": chunk.is_final,
                    "created_at": chunk.created_at.isoformat(),
                }
                yield f"id: {chunk.sequence}\\ndata: {json.dumps(payload_data, default=str)}\\n\\n"
                next_sequence += 1
                if chunk.is_final:
                    return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
