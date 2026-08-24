from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_subject, get_db_session, get_optional_subject, require_scope
from app.schemas.marketplace import (
    BillingWebhookRequest,
    MarketplaceEscrowActionRequest,
    MarketplaceEscrowCreateRequest,
    MarketplaceEscrowResponse,
    MarketplaceListingRequest,
    MarketplaceListingResponse,
    MarketplaceSearchResponse,
    TierUpdateRequest,
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
    _payload: Annotated[dict | None, Depends(get_optional_subject)],
):
    listing = await marketplace_service.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return MarketplaceListingResponse(**listing)


@router.get("/listings", response_model=MarketplaceSearchResponse)
async def search_listings(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict | None, Depends(get_optional_subject)],
    capability: str | None = None,
    min_trust_score: float | None = None,
    access_tier: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    max_latency_p95_ms: int | None = None,
    limit: int = 20,
    offset: int = 0,
):
    result = await marketplace_service.search_listings(
        db,
        capability=capability,
        min_trust_score=min_trust_score,
        access_tier=access_tier,
        min_price=min_price,
        max_price=max_price,
        max_latency_p95_ms=max_latency_p95_ms,
        limit=limit,
        offset=offset,
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


@router.put("/listings/{listing_id}/tier", response_model=MarketplaceListingResponse)
async def update_tier(
    listing_id: str,
    body: TierUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:update"))],
):
    agent_id = payload.get("agent_id", "")
    existing = await marketplace_service.get_listing(db, listing_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if existing["agent_id"] != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the listing owner")
    try:
        result = await marketplace_service.set_access_tier(
            db, agent_id, body.access_tier, body.tier_details
        )
        return MarketplaceListingResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/listings/{listing_id}/metering")
async def get_metering(
    listing_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict | None, Depends(get_optional_subject)],
    agent_id: str | None = None,
):
    try:
        result = await marketplace_service.get_metering(db, listing_id, agent_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/escrows", response_model=MarketplaceEscrowResponse, status_code=status.HTTP_201_CREATED
)
async def create_escrow(
    body: MarketplaceEscrowCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:escrow"))],
):
    try:
        result = await marketplace_service.create_escrow(
            db,
            buyer_agent_id=payload.get("agent_id", ""),
            listing_id=body.listing_id,
            amount=body.amount,
            currency=body.currency,
            task_id=body.task_id,
            provider_reference=body.provider_reference,
            idempotency_key=body.idempotency_key,
            metadata=body.metadata,
        )
        return MarketplaceEscrowResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/escrows/{escrow_id}", response_model=MarketplaceEscrowResponse)
async def get_escrow(
    escrow_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:escrow"))],
):
    try:
        result = await marketplace_service.get_escrow(db, escrow_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow not found")
    actor_id = payload.get("agent_id", "")
    if actor_id not in (result["buyer_agent_id"], result["seller_agent_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an escrow participant")
    return MarketplaceEscrowResponse(**result)


@router.post("/escrows/{escrow_id}/release", response_model=MarketplaceEscrowResponse)
async def release_escrow(
    escrow_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:escrow"))],
):
    try:
        result = await marketplace_service.release_escrow(db, escrow_id, payload.get("agent_id", ""))
        return MarketplaceEscrowResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Escrow not found" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/escrows/{escrow_id}/dispute", response_model=MarketplaceEscrowResponse)
async def dispute_escrow(
    escrow_id: str,
    body: MarketplaceEscrowActionRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("marketplace:escrow"))],
):
    try:
        result = await marketplace_service.dispute_escrow(
            db, escrow_id, payload.get("agent_id", ""), body.reason
        )
        return MarketplaceEscrowResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Escrow not found" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/escrows/{escrow_id}/refund", response_model=MarketplaceEscrowResponse)
async def refund_escrow(
    escrow_id: str,
    body: MarketplaceEscrowActionRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
):
    try:
        result = await marketplace_service.refund_escrow(
            db, escrow_id, body.reason, payload.get("agent_id")
        )
        return MarketplaceEscrowResponse(**result)
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Escrow not found" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/webhooks/billing", status_code=status.HTTP_202_ACCEPTED)
async def billing_webhook(
    body: BillingWebhookRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict | None, Depends(get_optional_subject)],
):
    try:
        result = await marketplace_service.record_usage(
            db, body.listing_id, body.agent_id, body.calls
        )
        return {**result, "event_type": body.event_type, "accepted": True}
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
