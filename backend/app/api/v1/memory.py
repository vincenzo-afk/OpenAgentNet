from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.memory import (
    MemoryListResponse,
    MemoryObjectResponse,
    MemoryWriteRequest,
)
from app.services.memory import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])
memory_service = MemoryService()


@router.post("", response_model=MemoryObjectResponse, status_code=status.HTTP_201_CREATED)
async def write_memory(
    body: MemoryWriteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("memory:write"))],
):
    try:
        agent_id = payload.get("agent_id", "")
        result = await memory_service.write_memory(
            db,
            owner_agent_id=agent_id,
            namespace=body.namespace,
            key=body.key,
            data=body.data,
            permissions=[p.model_dump() for p in body.permissions] if body.permissions else None,
            ephemeral=body.ephemeral,
            ttl_seconds=body.ttl_seconds,
        )
        return MemoryObjectResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{memory_id}", response_model=MemoryObjectResponse)
async def read_memory(
    memory_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("memory:read"))],
):
    agent_id = payload.get("agent_id", "")
    memory = await memory_service.read_memory(db, agent_id, memory_id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return MemoryObjectResponse(**memory)


@router.get("", response_model=MemoryListResponse)
async def list_memory(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("memory:read"))],
    namespace: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    agent_id = payload.get("agent_id", "")
    result = await memory_service.list_memory(
        db, agent_id=agent_id, namespace=namespace, limit=limit, offset=offset
    )
    return MemoryListResponse(**result)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("memory:write"))],
):
    agent_id = payload.get("agent_id", "")
    try:
        await memory_service.delete_memory(db, agent_id, memory_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
