from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_subject, get_db_session, require_scope
from app.schemas.agent import (
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
    RegistrationRequest,
    RegistrationResponse,
)
from app.services.messaging import MessagingService
from app.services.registry import RegistryService

router = APIRouter(tags=["agents"])
registry_service = RegistryService()
messaging_service = MessagingService()


@router.post(
    "/agents/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_agent(
    body: RegistrationRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        result = await registry_service.register(
            db,
            manifest=body.identity,
            proof=body.proof.model_dump(),
        )
        return RegistrationResponse(**result)
    except ValueError as e:
        detail = str(e)
        if "already registered" in detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(get_current_subject)],
):
    agent = await registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return AgentResponse(**agent)


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("agent:update"))],
):
    updates = body.model_dump(exclude_unset=True)
    try:
        result = await registry_service.update_agent(db, agent_id, updates)
        return AgentResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("agent:update"))],
):
    try:
        await registry_service.deregister_agent(db, agent_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("admin"))],
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    result = await registry_service.list_agents(
        db, status=status_filter, limit=limit, offset=offset
    )
    return AgentListResponse(**result)


@router.post("/agents/{agent_id}/heartbeat")
async def send_heartbeat(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("agent:update"))],
):
    try:
        result = await messaging_service.send_heartbeat(db, agent_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/agents/{agent_id}/rotate-key")
async def rotate_key(
    agent_id: str,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("agent:update"))],
):
    new_public_key = body.get("public_key", "")
    if not new_public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="public_key is required",
        )
    try:
        result = await registry_service.rotate_key(db, agent_id, new_public_key)
        return result
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
