from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.team import (
    TeamCreateRequest,
    TeamListResponse,
    TeamMemberRequest,
    TeamResponse,
)
from app.services.team import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])
team_service = TeamService()


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("team:write"))],
):
    try:
        result = await team_service.create_team(
            db,
            owner_agent_id=payload.get("agent_id", ""),
            name=body.name,
            description=body.description,
            member_agent_ids=body.member_agent_ids,
        )
        return TeamResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=TeamListResponse)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("team:read"))],
    limit: int = 20,
    offset: int = 0,
):
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination")
    return TeamListResponse(**await team_service.list_teams(db, limit=limit, offset=offset))


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("team:read"))],
):
    try:
        result = await team_service.get_team(db, team_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamResponse(**result)


@router.post("/{team_id}/members", response_model=TeamResponse)
async def add_member(
    team_id: str,
    body: TeamMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("team:write"))],
):
    try:
        result = await team_service.add_member(
            db, team_id, payload.get("agent_id", ""), body.agent_id
        )
        return TeamResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Team not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))


@router.delete("/{team_id}/members/{agent_id}", response_model=TeamResponse)
async def remove_member(
    team_id: str,
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("team:write"))],
):
    try:
        result = await team_service.remove_member(
            db, team_id, payload.get("agent_id", ""), agent_id
        )
        return TeamResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Team not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))
