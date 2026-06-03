from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.negotiation import (
    NegotiationDetail,
    NegotiationProposalRequest,
    NegotiationProposalResponse,
    NegotiationRespondRequest,
    NegotiationResponseSchema,
)
from app.services.negotiation import NegotiationService

router = APIRouter(prefix="/negotiations", tags=["negotiations"])
negotiation_service = NegotiationService()


@router.post("", response_model=NegotiationProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    body: NegotiationProposalRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("negotiate:create"))],
):
    try:
        requester_id = payload.get("agent_id", "")
        result = await negotiation_service.create_proposal(
            db,
            requester_id=requester_id,
            target_id=body.target_id,
            proposal=body.model_dump(),
        )
        return NegotiationProposalResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{negotiation_id}/respond", response_model=NegotiationResponseSchema)
async def respond_to_negotiation(
    negotiation_id: str,
    body: NegotiationRespondRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("negotiate:respond"))],
):
    try:
        result = await negotiation_service.respond(
            db,
            negotiation_id=negotiation_id,
            response=body.model_dump(),
        )
        return NegotiationResponseSchema(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{negotiation_id}", response_model=NegotiationDetail)
async def get_negotiation(
    negotiation_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("negotiate:read"))],
):
    negotiation = await negotiation_service.get_negotiation(db, negotiation_id)
    if not negotiation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Negotiation not found")
    return NegotiationDetail(**negotiation)
