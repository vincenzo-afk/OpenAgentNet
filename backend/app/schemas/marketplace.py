from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class MarketplaceListingRequest(BaseModel):
    title: str
    long_description: str | None = None
    pricing: dict[str, Any] = {}
    sla: dict[str, Any] = {}
    tiers: list[dict[str, Any]] = []
    access_tier: str = "free"
    tier_details: dict[str, Any] = {}
    is_public: bool = True


class MarketplaceListingResponse(BaseModel):
    id: str
    agent_id: str
    title: str
    long_description: str | None = None
    pricing: dict[str, Any]
    sla: dict[str, Any]
    tiers: list[dict[str, Any]]
    access_tier: str
    tier_details: dict[str, Any]
    is_public: bool
    is_featured: bool
    view_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MarketplaceSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MarketplaceListingResponse]


class TierUpdateRequest(BaseModel):
    access_tier: str
    tier_details: dict[str, Any] | None = None


class MarketplaceEscrowCreateRequest(BaseModel):
    listing_id: str
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=1, max_length=12)
    task_id: str | None = None
    provider_reference: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = {}


class MarketplaceEscrowActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class MarketplaceEscrowResponse(BaseModel):
    escrow_id: str
    listing_id: str
    buyer_agent_id: str
    seller_agent_id: str
    task_id: str | None = None
    amount: Decimal
    currency: str
    status: str
    provider_reference: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    settled_at: datetime | None = None


class BillingWebhookRequest(BaseModel):
    listing_id: str
    agent_id: str
    calls: int = 1
    event_type: str = "usage"
    idempotency_key: str | None = None
