from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryObject, MemoryPermission


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryService:
    async def write_memory(
        self,
        db: AsyncSession,
        owner_agent_id: str,
        namespace: str,
        key: str,
        data: dict[str, Any],
        data_type: str = "json",
        permissions: list[dict[str, Any]] | None = None,
        ephemeral: bool = False,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        # Check for existing memory with same owner/namespace/key
        result = await db.execute(
            select(MemoryObject).where(
                MemoryObject.owner_agent_id == uuid.UUID(owner_agent_id),
                MemoryObject.namespace == namespace,
                MemoryObject.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing memory
            existing.data = data
            existing.data_type = data_type
            existing.is_ephemeral = ephemeral
            existing.version += 1
            existing.updated_at = utcnow()
            if ttl_seconds is not None:
                existing.expires_at = utcnow() + timedelta(seconds=ttl_seconds)
            memory = existing
        else:
            # Create new memory
            expires_at = None
            if ttl_seconds is not None:
                expires_at = utcnow() + timedelta(seconds=ttl_seconds)

            memory = MemoryObject(
                namespace=namespace,
                key=key,
                owner_agent_id=uuid.UUID(owner_agent_id),
                data=data,
                data_type=data_type,
                is_ephemeral=ephemeral,
                expires_at=expires_at,
            )
            db.add(memory)
            await db.flush()

        # Add permissions if provided
        if permissions:
            for perm in permissions:
                grantee_id = uuid.UUID(perm["grantee_agent_id"])
                # Check for existing permission
                existing_perm = await db.execute(
                    select(MemoryPermission).where(
                        MemoryPermission.memory_id == memory.id,
                        MemoryPermission.grantee_agent_id == grantee_id,
                    )
                )
                if not existing_perm.scalar_one_or_none():
                    permission = MemoryPermission(
                        memory_id=memory.id,
                        grantee_agent_id=grantee_id,
                        permission=perm["permission"],
                    )
                    db.add(permission)

        await db.flush()
        return self._memory_to_dict(memory)

    async def read_memory(
        self, db: AsyncSession, agent_id: str, memory_id: str
    ) -> dict[str, Any] | None:
        result = await db.execute(
            select(MemoryObject).where(MemoryObject.id == uuid.UUID(memory_id))
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return None

        # Check access: owner or has permission
        if str(memory.owner_agent_id) != agent_id:
            perm_result = await db.execute(
                select(MemoryPermission).where(
                    MemoryPermission.memory_id == memory.id,
                    MemoryPermission.grantee_agent_id == uuid.UUID(agent_id),
                )
            )
            if not perm_result.scalar_one_or_none():
                return None

        # Check expiry
        if memory.expires_at and memory.expires_at < utcnow():
            return None

        return self._memory_to_dict(memory)

    async def list_memory(
        self,
        db: AsyncSession,
        agent_id: str,
        namespace: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(MemoryObject).where(MemoryObject.owner_agent_id == uuid.UUID(agent_id))
        count_query = select(func.count(MemoryObject.id)).where(
            MemoryObject.owner_agent_id == uuid.UUID(agent_id)
        )

        if namespace:
            query = query.where(MemoryObject.namespace == namespace)
            count_query = count_query.where(MemoryObject.namespace == namespace)

        # Filter out expired memories
        query = query.where(
            (MemoryObject.expires_at.is_(None)) | (MemoryObject.expires_at > utcnow())
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(MemoryObject.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        memories = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._memory_to_dict(m) for m in memories],
        }

    async def delete_memory(self, db: AsyncSession, agent_id: str, memory_id: str) -> None:
        result = await db.execute(
            select(MemoryObject).where(
                MemoryObject.id == uuid.UUID(memory_id),
                MemoryObject.owner_agent_id == uuid.UUID(agent_id),
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            raise ValueError("Memory not found or not owned by agent")
        await db.delete(memory)
        await db.flush()

    def _memory_to_dict(self, memory: MemoryObject) -> dict[str, Any]:
        return {
            "id": str(memory.id),
            "namespace": memory.namespace,
            "key": memory.key,
            "owner_agent_id": str(memory.owner_agent_id),
            "data": memory.data,
            "data_type": memory.data_type,
            "is_ephemeral": memory.is_ephemeral,
            "version": memory.version,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
        }
