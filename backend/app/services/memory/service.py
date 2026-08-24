from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identifiers import parse_agent_id
from app.core.nats_client import publish_event
from app.models.memory import MemoryObject, MemoryPermission


def utcnow() -> datetime:
    return datetime.now(UTC)


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
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        if embedding is not None and len(embedding) != 1536:
            raise ValueError("embedding must contain exactly 1536 dimensions")

        # Namespace isolation (Phase 5 deliverable): an agent may only write
        # memories into its own namespace space. When the namespace is
        # namespaced by agent id (``agent:<agent_id>``) it must match the
        # requesting agent; existing memories may never be hijacked.
        resolved_owner = parse_agent_id(owner_agent_id)
        if not resolved_owner:
            raise ValueError("Invalid agent_id")
        requested_ns_agent = str(resolved_owner)
        if str(namespace).strip().lower().startswith("agent:"):
            ns_owner = str(namespace).strip()[6:].strip().lower()
            if ns_owner != requested_ns_agent:
                raise ValueError(
                    "Namespace isolation violation: agent may only write to its own namespace"
                )

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
            if str(existing.owner_agent_id) != requested_ns_agent:
                raise ValueError("Memory namespace isolation: not owned by requesting agent")
            existing.data = data
            existing.data_type = data_type
            existing.is_ephemeral = ephemeral
            existing.embedding = embedding
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
                embedding=embedding,
            )
            db.add(memory)
            await db.flush()

        # Stream the new memory object over NATS (Phase 5 deliverable)
        await publish_event(
            "memory.created",
            {
                "memory_id": str(memory.id),
                "namespace": memory.namespace,
                "key": memory.key,
                "owner_agent_id": str(memory.owner_agent_id),
                "version": memory.version,
                "timestamp": utcnow().isoformat(),
            },
        )

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

        # Stream the memory update over NATS (Phase 5 deliverable)
        await publish_event(
            "memory.updated",
            {
                "memory_id": str(memory.id),
                "namespace": memory.namespace,
                "key": memory.key,
                "owner_agent_id": str(memory.owner_agent_id),
                "version": memory.version,
                "timestamp": utcnow().isoformat(),
            },
        )

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

        # ACL enforcement (Phase 5 deliverable): only the owner or an
        # explicitly granted agent may read a memory object.
        owner_uuid = parse_agent_id(agent_id)
        if str(memory.owner_agent_id) != str(owner_uuid or agent_id) and str(memory.owner_agent_id) != agent_id:
            perm_result = await db.execute(
                select(MemoryPermission).where(
                    MemoryPermission.memory_id == memory.id,
                    MemoryPermission.grantee_agent_id == parse_agent_id(agent_id),
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
        query = select(MemoryObject).where(MemoryObject.owner_agent_id == parse_agent_id(agent_id))
        count_query = select(func.count(MemoryObject.id)).where(
            MemoryObject.owner_agent_id == parse_agent_id(agent_id)
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

    async def search_memory(
        self,
        db: AsyncSession,
        agent_id: str,
        embedding: list[float],
        namespace: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search an agent's non-expired embedded memories by cosine similarity."""
        if len(embedding) != 1536:
            raise ValueError("embedding must contain exactly 1536 dimensions")
        owner = parse_agent_id(agent_id)
        if owner is None:
            raise ValueError("Invalid agent_id")
        active_filter = (
            (MemoryObject.owner_agent_id == owner)
            & MemoryObject.embedding.is_not(None)
            & ((MemoryObject.expires_at.is_(None)) | (MemoryObject.expires_at > utcnow()))
        )
        count_query = select(func.count(MemoryObject.id)).where(active_filter)
        query = select(
            MemoryObject,
            (1 - MemoryObject.embedding.cosine_distance(embedding)).label("similarity"),
        ).where(active_filter)
        if namespace:
            query = query.where(MemoryObject.namespace == namespace)
            count_query = count_query.where(MemoryObject.namespace == namespace)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        result = await db.execute(
            query.order_by(MemoryObject.embedding.cosine_distance(embedding))
            .offset(offset)
            .limit(limit)
        )
        items = []
        for memory, similarity in result.all():
            item = self._memory_to_dict(memory)
            item["similarity"] = round(float(similarity), 6)
            items.append(item)
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    async def update_memory(
        self,
        db: AsyncSession,
        agent_id: str,
        memory_id: str,
        data: dict[str, Any] | None = None,
        data_type: str | None = None,
        permissions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing memory object (owner only).

        ``permissions`` replaces the current grant list when provided.
        """
        result = await db.execute(
            select(MemoryObject).where(
                MemoryObject.id == uuid.UUID(memory_id),
                MemoryObject.owner_agent_id == parse_agent_id(agent_id),
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            raise ValueError("Memory not found or not owned by agent")

        if data is not None:
            memory.data = data
        if data_type is not None:
            memory.data_type = data_type
        memory.version += 1
        memory.updated_at = utcnow()

        if permissions is not None:
            # Replace grants: remove existing, add new
            await db.execute(
                MemoryPermission.__table__.delete().where(
                    MemoryPermission.memory_id == memory.id
                )
            )
            for perm in permissions:
                grantee_id = parse_agent_id(perm["grantee_agent_id"])
                if grantee_id is None:
                    raise ValueError("Invalid grantee_agent_id")
                db.add(
                    MemoryPermission(
                        memory_id=memory.id,
                        grantee_agent_id=grantee_id,
                        permission=perm.get("permission", "read"),
                    )
                )

        await db.flush()
        await db.commit()
        return self._memory_to_dict(memory)

    async def delete_memory(self, db: AsyncSession, agent_id: str, memory_id: str) -> None:
        result = await db.execute(
            select(MemoryObject).where(
                MemoryObject.id == uuid.UUID(memory_id),
                MemoryObject.owner_agent_id == parse_agent_id(agent_id),
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            raise ValueError("Memory not found or not owned by agent")
        await db.delete(memory)
        await db.flush()

        # Stream the deletion over NATS (Phase 5 deliverable)
        await publish_event(
            "memory.deleted",
            {
                "memory_id": str(memory.id),
                "namespace": memory.namespace,
                "owner_agent_id": str(memory.owner_agent_id),
                "timestamp": utcnow().isoformat(),
            },
        )

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
