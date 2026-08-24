from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.routing import RoutingRequest, RoutingResponse
from app.services.routing import RoutingService

router = APIRouter(prefix="/routing", tags=["routing"])
routing_service = RoutingService()


@router.post("/route", response_model=RoutingResponse)
async def route_task(
    body: RoutingRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _payload: Annotated[dict, Depends(require_scope("tasks:initiate"))],
):
    result = await routing_service.route(
        db,
        task_description=body.task_description,
        required_capabilities=body.required_capabilities,
        constraints=body.constraints,
        limit=body.limit,
    )
    return RoutingResponse(**result)
