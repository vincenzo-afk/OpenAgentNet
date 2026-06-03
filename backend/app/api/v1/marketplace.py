from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, get_current_subject, require_scope
from app.schemas.marketplace import (
    MarketplaceListingRequest,
    MarketplaceListingResponse,
    MarketplaceSearchResponse,
)
from app.services.marketplace import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])
marketplace_service = MarketplaceService()


@router.post(
    "/listings", response_model=MarketplaceListingResponse, status_code=status.HTTP_201_CREATED
)
async def create_listing(
    body: MarketplaceListingRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:create"))],
):
    try:
        agent_id = payload.get("agent_id", "")
        result = await marketplace_service.create_listing(db, agent_id, body.model_dump())
        return MarketplaceListingResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/listings/{listing_id}", response_model=MarketplaceListingResponse)
async def get_listing(
    listing_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(get_current_subject)],
):
    listing = await marketplace_service.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return MarketplaceListingResponse(**listing)


@router.get("/listings", response_model=MarketplaceSearchResponse)
async def search_listings(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(get_current_subject)],
    capability: str | None = None,
    min_trust_score: float | None = None,
    limit: int = 20,
    offset: int = 0,
):
    result = await marketplace_service.search_listings(
        db, capability=capability, min_trust_score=min_trust_score, limit=limit, offset=offset
    )
    return MarketplaceSearchResponse(**result)


@router.put("/listings", response_model=MarketplaceListingResponse)
async def update_listing(
    body: MarketplaceListingRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:update"))],
):
    try:
        agent_id = payload.get("agent_id", "")
        result = await marketplace_service.update_listing(db, agent_id, body.model_dump())
        return MarketplaceListingResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/listings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:delete"))],
):
    agent_id = payload.get("agent_id", "")
    try:
        await marketplace_service.delete_listing(db, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
