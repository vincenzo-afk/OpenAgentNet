from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_subject, get_db_session, require_scope
from app.schemas.discovery import (
    DiscoverySearchRequest,
    DiscoverySearchResponse,
)
from app.services.discovery import DiscoveryService

router = APIRouter(tags=["discovery"])
discovery_service = DiscoveryService()


@router.post("/discovery/search", response_model=DiscoverySearchResponse)
async def search_agents(
    body: DiscoverySearchRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("discovery:read"))],
):
    filters = dict(body.filters)
    if body.region:
        filters["region"] = body.region
    result = await discovery_service.search(
        db,
        capabilities=body.capabilities,
        filters=filters,
        sort=body.sort,
        limit=body.limit,
        offset=body.offset,
    )
    return DiscoverySearchResponse(**result)


@router.get("/discover")
async def discover_agents(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(get_current_subject)],
    capability: str | None = None,
    tags: str | None = None,
    min_trust_score: float | None = None,
    max_latency_p95_ms: int | None = None,
    max_latency_ms: int | None = None,
    language: str | None = None,
    exclude: str | None = None,
    status: str | None = None,
    region: str | None = None,
    limit: int = 10,
    sort: str = "trust_score:desc",
):
    filters = {}
    if min_trust_score is not None:
        filters["min_trust_score"] = min_trust_score
    if max_latency_p95_ms is not None:
        filters["max_latency_p95_ms"] = max_latency_p95_ms
    elif max_latency_ms is not None:
        filters["max_latency_p95_ms"] = max_latency_ms
    if language:
        filters["language"] = language
    if exclude:
        filters["exclude"] = [item for item in exclude.split(",") if item]
    if tags:
        filters["tags"] = tags.split(",")
    if status is not None:
        filters["status"] = status
    if region is not None:
        filters["region"] = region

    result = await discovery_service.search(
        db,
        capabilities=[capability] if capability else None,
        filters=filters,
        sort=sort,
        limit=limit,
    )
    return result
