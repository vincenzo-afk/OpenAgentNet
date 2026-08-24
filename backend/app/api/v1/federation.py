from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.federation import (
    AgentMigrationRequest,
    AgentMigrationResponse,
    RegistryPeerCreate,
    RegistryPeerCreatedResponse,
    RegistryPeerResponse,
    RegistrySyncRequest,
    RegistrySyncResponse,
)
from app.services.federation import FederationService

router = APIRouter(prefix="/federation", tags=["federation"])
federation_service = FederationService()


@router.post(
    "/registries",
    response_model=RegistryPeerCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registry_peer(
    body: RegistryPeerCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _operator: Annotated[dict, Depends(require_scope("admin"))],
):
    try:
        peer, shared_secret = await federation_service.create_peer(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {**peer, "shared_secret": shared_secret}


@router.get("/registries", response_model=list[RegistryPeerResponse])
async def list_registry_peers(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _operator: Annotated[dict, Depends(require_scope("admin"))],
):
    return await federation_service.list_peers(db)


@router.post("/registries/{registry_id}/sync", response_model=RegistrySyncResponse)
async def sync_registry(
    registry_id: str,
    body: RegistrySyncRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    federation_token: Annotated[str | None, Header(alias="X-Federation-Token")] = None,
):
    if not federation_token:
        raise HTTPException(status_code=401, detail="Missing federation token")
    peer = await federation_service.authenticate_peer(db, registry_id, federation_token)
    if not peer:
        raise HTTPException(status_code=401, detail="Invalid federation credentials")
    try:
        return await federation_service.sync_registry(db, peer, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/migrate", response_model=AgentMigrationResponse)
async def migrate_agent(
    agent_id: str,
    body: AgentMigrationRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _operator: Annotated[dict, Depends(require_scope("admin"))],
):
    migrated = await federation_service.migrate_agent(db, agent_id, body)
    if not migrated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return migrated
