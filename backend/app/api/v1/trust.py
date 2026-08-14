from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Header
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, get_optional_subject, require_scope
from app.schemas.trust import (
    DisputeListResponse,
    DisputeRequest,
    DisputeResolveRequest,
    DisputeResponse,
    EndorsementRequest,
    EndorsementResponse,
    TrustEventsResponse,
    TrustScoreResponse,
)


def _verify_operator_secret(secret: str | None) -> bool:
    expected = os.environ.get("OPERATOR_SECRET", "")
    return bool(expected) and secret == expected

from app.services.trust import TrustService

router = APIRouter(prefix="/trust", tags=["trust"])
trust_service = TrustService()


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


@router.post("/disputes/{dispute_id}/mark-review")
async def mark_dispute_under_review(
    dispute_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
):
    try:
        return await trust_service.mark_dispute_under_review(db, dispute_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    body: DisputeResolveRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    operator_secret: Annotated[str | None, Header(alias="X-Operator-Secret")] = None,
):
    """Resolve a dispute. Requires a matching OPERATOR_SECRET header/env var."""
    if not _verify_operator_secret(operator_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing operator secret",
        )
    try:
        return await trust_service.resolve_dispute(
            db, dispute_id=dispute_id, verdict=body.verdict,
            resolution_notes=body.resolution_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/disputes", response_model=DisputeListResponse)
async def list_disputes(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    result = await trust_service.list_disputes(
        db, status=status_filter, limit=limit, offset=offset
    )
    return DisputeListResponse(**result)


@router.get("/{agent_id}", response_model=TrustScoreResponse)
async def get_trust_score(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict | None, Depends(get_optional_subject)],
):
    record = await trust_service.get_trust_record(db, agent_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust record not found")
    return TrustScoreResponse(**record)


@router.get("/{agent_id}/events", response_model=TrustEventsResponse)
async def get_trust_events(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict | None, Depends(get_optional_subject)],
    limit: int = 50,
):
    events = await trust_service.get_events(db, agent_id, limit=limit)
    return TrustEventsResponse(events=events)
