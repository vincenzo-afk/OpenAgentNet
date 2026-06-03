from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_subject, get_db_session, require_scope
from app.core.security import (
    create_access_token,
    decode_token,
)
from app.core.security import (
    revoke_token as revoke_jwt_token,
)
from app.models.agent import Agent
from app.models.audit import AuditEvent
from app.schemas.common import (
    AuditEventResponse,
    AuditListResponse,
    HealthResponse,
    SuspendRequest,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.services.registry import RegistryService

router = APIRouter(tags=["admin"])
registry_service = RegistryService()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@router.get("/admin/agents")
async def admin_list_agents(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    result = await registry_service.list_agents(
        db, status=status_filter, limit=limit, offset=offset
    )
    return result


@router.post("/admin/agents/{agent_id}/suspend")
async def suspend_agent(
    agent_id: str,
    body: SuspendRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
):
    try:
        await registry_service.update_agent(db, agent_id, {"status": "suspended"})
        # Audit log
        actor_id = None
        sub = payload.get("sub", "")
        try:
            actor_id = uuid.UUID(sub)
        except (ValueError, AttributeError):
            agent_result = await db.execute(select(Agent).where(Agent.did == sub))
            agent = agent_result.scalar_one_or_none()
            if agent:
                actor_id = agent.id
        audit = AuditEvent(
            event_type="agent_suspended",
            actor_id=actor_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            target_id=uuid.UUID(agent_id),
            target_type="agent",
            payload={"reason": body.reason},
        )
        db.add(audit)
        await db.flush()
        return {"status": "suspended", "agent_id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/admin/agents/{agent_id}/reinstate")
async def reinstate_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
):
    try:
        await registry_service.update_agent(db, agent_id, {"status": "active"})
        return {"status": "active", "agent_id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/admin/audit", response_model=AuditListResponse)
async def get_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("admin"))],
    agent_id: str | None = None,
    event_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    query = select(AuditEvent)
    count_query = select(func.count(AuditEvent.id))

    if agent_id:
        try:
            agent_uuid = uuid.UUID(agent_id)
            query = query.where(AuditEvent.actor_id == agent_uuid)
            count_query = count_query.where(AuditEvent.actor_id == agent_uuid)
        except (ValueError, AttributeError):
            pass
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
        count_query = count_query.where(AuditEvent.event_type == event_type)
    if since:
        query = query.where(AuditEvent.occurred_at >= since)
        count_query = count_query.where(AuditEvent.occurred_at >= since)
    if until:
        query = query.where(AuditEvent.occurred_at <= until)
        count_query = count_query.where(AuditEvent.occurred_at <= until)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(AuditEvent.occurred_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()

    items = [
        AuditEventResponse(
            id=e.id,
            event_type=e.event_type,
            actor_id=str(e.actor_id) if e.actor_id else None,
            target_id=str(e.target_id) if e.target_id else None,
            target_type=e.target_type,
            payload=e.payload,
            ip_address=e.ip_address,
            occurred_at=e.occurred_at.isoformat() if e.occurred_at else "",
        )
        for e in events
    ]

    return AuditListResponse(total=total, limit=limit, offset=offset, items=items)


@router.post("/auth/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    body: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_token = create_access_token(
        subject=payload["sub"],
        scopes=payload.get("scopes", []),
        extra_claims={"agent_id": payload.get("agent_id")},
    )

    expires_at = datetime.now(UTC) + timedelta(minutes=60)

    return TokenRefreshResponse(
        api_token=new_token,
        expires_at=expires_at.isoformat(),
    )


@router.delete("/auth/token", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_current_token(
    payload: Annotated[dict, Depends(get_current_subject)],
):
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        from datetime import datetime

        exp_dt = datetime.fromtimestamp(exp, tz=UTC)
        await revoke_jwt_token(jti, exp_dt)
    return None
