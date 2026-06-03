from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_scope
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.services.orchestration import OrchestrationService

router = APIRouter(prefix="/workflows", tags=["workflows"])
orchestration_service = OrchestrationService()


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("delegate:workflow"))],
):
    try:
        agent_id = payload.get("agent_id", "")
        result = await orchestration_service.create_workflow(
            db,
            owner_agent_id=agent_id,
            definition=body.definition.model_dump(),
            name=body.name,
        )
        return WorkflowResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("delegate:workflow"))],
):
    workflow = await orchestration_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowResponse(**workflow)


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[dict, Depends(require_scope("delegate:workflow"))],
    limit: int = 20,
    offset: int = 0,
):
    agent_id = payload.get("agent_id", "")
    result = await orchestration_service.list_workflows(
        db, agent_id=agent_id, limit=limit, offset=offset
    )
    return WorkflowListResponse(**result)
