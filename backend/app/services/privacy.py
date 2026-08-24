from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy_proofs import create_binary_outcome_proof, verify_binary_outcome_proof
from app.models.task import Task
from app.models.task_proof import TaskPrivacyProof


class PrivacyProofService:
    async def create(
        self,
        db: AsyncSession,
        task_id: str,
        actor_id: str,
        outcome: int,
        nonce: str,
    ) -> dict[str, Any]:
        task_uuid = self._parse_task_id(task_id)
        task_result = await db.execute(select(Task).where(Task.id == task_uuid))
        task = task_result.scalar_one_or_none()
        if not task:
            raise ValueError("Task not found")
        if actor_id not in (str(task.from_agent_id), str(task.to_agent_id)):
            raise PermissionError("Only task participants may create a proof")
        existing_result = await db.execute(
            select(TaskPrivacyProof).where(TaskPrivacyProof.task_id == task_uuid)
        )
        if existing_result.scalar_one_or_none():
            raise ValueError("A privacy proof already exists for this task")
        proof = create_binary_outcome_proof(task_id, outcome, nonce)
        record = TaskPrivacyProof(
            task_id=task_uuid,
            scheme=proof["scheme"],
            commitment=proof["commitment"],
            proof=proof,
        )
        db.add(record)
        await db.flush()
        return self._to_dict(record)

    async def verify(self, db: AsyncSession, task_id: str) -> dict[str, Any]:
        task_uuid = self._parse_task_id(task_id)
        result = await db.execute(
            select(TaskPrivacyProof).where(TaskPrivacyProof.task_id == task_uuid)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise ValueError("Privacy proof not found")
        return {
            "task_id": str(record.task_id),
            "valid": verify_binary_outcome_proof(record.proof),
            "scheme": record.scheme,
        }

    @staticmethod
    def _parse_task_id(task_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(task_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid task_id") from exc

    @staticmethod
    def _to_dict(record: TaskPrivacyProof) -> dict[str, Any]:
        return {
            "task_id": str(record.task_id),
            "scheme": record.scheme,
            "commitment": record.commitment,
            "proof": record.proof,
            "created_at": record.created_at.isoformat(),
        }
