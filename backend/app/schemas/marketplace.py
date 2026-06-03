from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class MarketplaceListingRequest(BaseModel):
    title: str
    long_description: Optional[str] = None
    pricing: dict[str, Any] = {}
    sla: dict[str, Any] = {}
    tiers: list[dict[str, Any]] = []
    is_public: bool = True


class MarketplaceListingResponse(BaseModel):
    id: str
    agent_id: str
    title: str
    long_description: Optional[str] = None
    pricing: dict[str, Any]
    sla: dict[str, Any]
    tiers: list[dict[str, Any]]
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
