from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


class BillingWebhookRequest(BaseModel):
    listing_id: str
    agent_id: str
    calls: int = 1
    event_type: str = "usage"
    idempotency_key: str | None = None
