from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.privacy import (
    TaskPrivacyProofCreateRequest,
    TaskPrivacyProofResponse,
    TaskPrivacyProofVerificationResponse,
)
from app.services.privacy import PrivacyProofService

router = APIRouter(prefix="/tasks", tags=["privacy proofs"])
privacy_service = PrivacyProofService()


@router.post("/{task_id}/privacy-proof", response_model=TaskPrivacyProofResponse, status_code=201)
async def create_privacy_proof(
    task_id: str,
    body: TaskPrivacyProofCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("messages:send"))],
):
    try:
        return await privacy_service.create(
            db,
            task_id=task_id,
            actor_id=payload.get("agent_id", ""),
            outcome=body.outcome,
            nonce=body.nonce,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        code = 409 if "already exists" in str(exc) else 400 if "Invalid" in str(exc) else 404
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/{task_id}/privacy-proof/verify", response_model=TaskPrivacyProofVerificationResponse)
async def verify_privacy_proof(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        return await privacy_service.verify(db, task_id)
    except ValueError as exc:
        code = 400 if "Invalid" in str(exc) else 404
        raise HTTPException(status_code=code, detail=str(exc)) from exc
