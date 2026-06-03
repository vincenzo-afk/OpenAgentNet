from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.trust import (
    DisputeRequest,
    DisputeResponse,
    EndorsementRequest,
    EndorsementResponse,
    TrustEventsResponse,
    TrustScoreResponse,
)
from app.services.trust import TrustService

router = APIRouter(prefix="/trust", tags=["trust"])
trust_service = TrustService()


@router.get("/{agent_id}", response_model=TrustScoreResponse)
async def get_trust_score(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("trust:read"))],
):
    record = await trust_service.get_trust_record(db, agent_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust record not found")
    return TrustScoreResponse(**record)


@router.get("/{agent_id}/events", response_model=TrustEventsResponse)
async def get_trust_events(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("trust:read"))],
    limit: int = 50,
):
    events = await trust_service.get_events(db, agent_id, limit=limit)
    return TrustEventsResponse(events=events)


@router.post("/endorse", response_model=EndorsementResponse, status_code=status.HTTP_201_CREATED)
async def endorse_agent(
    body: EndorsementRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("endorse:agent"))],
):
    try:
        from_agent_id = payload.get("agent_id", "")
        result = await trust_service.endorse(
            db,
            from_agent_id=from_agent_id,
            to_agent_id=body.to_agent_id,
            capability=body.capability,
            comment=body.comment,
        )
        return EndorsementResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/disputes", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def create_dispute(
    body: DisputeRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("trust:flag"))],
):
    try:
        reporter_agent_id = payload.get("agent_id", "")
        result = await trust_service.flag(
            db,
            reported_agent_id=body.reported_agent_id,
            reporter_agent_id=reporter_agent_id,
            reason=body.reason,
            task_id=body.task_id,
        )
        return DisputeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
