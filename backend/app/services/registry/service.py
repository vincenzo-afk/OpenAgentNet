from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.crypto import (
    base64_to_public_key,
    canonical_json_bytes,
    compute_agent_id_from_bytes,
    generate_api_key,
    hash_api_key,
    public_key_to_bytes,
    verify_signature,
)
from app.core.security import create_access_token
from app.models.agent import Agent, ApiKey
from app.schemas.agent import AgentManifest


def utcnow() -> datetime:
    return datetime.now(UTC)


class RegistryService:
    async def register(
        self, db: AsyncSession, manifest: AgentManifest, proof: dict[str, str]
    ) -> dict[str, Any]:
        # Parse public key
        public_key = base64_to_public_key(manifest.public_key)
        pk_bytes = public_key_to_bytes(public_key)

        # Compute deterministic agent_id from public key (per DESIGN.md)
        agent_id = compute_agent_id_from_bytes(pk_bytes)
        did = f"did:oan:{agent_id}"
        key_id = f"{did}#key-1"

        # Verify proof signature
        canonical = canonical_json_bytes(manifest.model_dump())
        timestamp = proof["timestamp"].encode()
        payload = canonical + timestamp
        sig_valid = verify_signature(public_key, proof["signature"], payload)
        if not sig_valid:
            raise ValueError("Invalid registration proof signature")

        # Check for duplicate by agent_id or public key
        existing = await db.execute(
            select(Agent).where(
                (Agent.id == uuid.UUID(agent_id)) | (Agent.public_key == manifest.public_key)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent with this public key already registered")

        agent = Agent(
            id=uuid.UUID(agent_id),
            did=did,
            name=manifest.name,
            display_name=manifest.display_name,
            version=manifest.version,
            description=manifest.description,
            owner_id=uuid.UUID(manifest.owner.get("id", str(uuid.uuid4()))),
            owner_type=manifest.owner.get("type", "user"),
            status="active",
            endpoint=manifest.endpoint,
            health_endpoint=manifest.health_endpoint,
            public_key=manifest.public_key,
            key_id=key_id,
            protocol_version=manifest.protocol_version,
            capabilities=[c.model_dump() for c in manifest.capabilities],
            permissions_required=manifest.permissions_required,
            permissions_offered=manifest.permissions_offered,
            tags=manifest.tags,
            metadata_=manifest.metadata,
        )
        db.add(agent)

        # Generate API key
        raw_api_key = generate_api_key()
        api_key = ApiKey(
            agent_id=agent.id,
            key_hash=hash_api_key(raw_api_key),
            key_prefix=raw_api_key[:12],
            is_active=True,
        )
        db.add(api_key)
        await db.flush()

        # Audit log: agent registered (SECURITY.md requirement)
        await log_audit_event(
            db,
            event_type="agent_registered",
            actor_id=agent.id,
            target_id=agent.id,
            target_type="agent",
            payload={"name": manifest.name, "did": did},
        )

        # Create JWT token
        token = create_access_token(
            subject=did,
            scopes=["agent:all"],
            extra_claims={"agent_id": agent_id},
        )

        return {
            "agent_id": agent_id,
            "did": did,
            "api_token": token,
            "registered_at": utcnow(),
            "status": "active",
        }

    async def get_agent(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        result = await db.execute(
            select(Agent).where(
                Agent.id == uuid.UUID(agent_id),
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return None
        return self._agent_to_dict(agent)

    async def get_agent_by_did(self, db: AsyncSession, did: str) -> Agent | None:
        result = await db.execute(
            select(Agent).where(
                Agent.did == did,
                Agent.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def update_agent(
        self, db: AsyncSession, agent_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        result = await db.execute(
            select(Agent).where(
                Agent.id == uuid.UUID(agent_id),
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        immutable_fields = {"id", "did", "public_key", "key_id", "protocol_version"}
        for key, value in updates.items():
            if value is not None and key not in immutable_fields:
                if key == "capabilities":
                    agent.capabilities = [
                        c if isinstance(c, dict) else c.model_dump() for c in value
                    ]
                elif key == "metadata":
                    agent.metadata_ = value
                elif hasattr(agent, key):
                    setattr(agent, key, value)

        agent.updated_at = utcnow()
        await db.flush()
        return self._agent_to_dict(agent)

    async def deregister_agent(self, db: AsyncSession, agent_id: str) -> None:
        result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")
        agent.status = "deregistered"
        agent.deleted_at = utcnow()
        agent.updated_at = utcnow()

    async def list_agents(
        self,
        db: AsyncSession,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = select(Agent).where(Agent.deleted_at.is_(None))
        count_query = select(func.count(Agent.id)).where(Agent.deleted_at.is_(None))

        if status:
            query = query.where(Agent.status == status)
            count_query = count_query.where(Agent.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._agent_to_dict(a) for a in agents],
        }

    async def verify_agent_signature(
        self, db: AsyncSession, agent_id: str, message: bytes, signature: str
    ) -> bool:
        agent = await self.get_agent(db, agent_id)
        if not agent:
            return False
        public_key = base64_to_public_key(agent["public_key"])
        return verify_signature(public_key, signature, message)

    async def rotate_key(
        self, db: AsyncSession, agent_id: str, new_public_key: str
    ) -> dict[str, Any]:
        """Rotate an agent's public key (SECURITY.md requirement)."""
        result = await db.execute(
            select(Agent).where(
                Agent.id == uuid.UUID(agent_id),
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        new_pk = base64_to_public_key(new_public_key)
        new_pk_bytes = public_key_to_bytes(new_pk)
        new_did = f"did:oan:{compute_agent_id_from_bytes(new_pk_bytes)}"

        # Check no other agent uses this key
        existing = await db.execute(
            select(Agent).where(
                Agent.public_key == new_public_key,
                Agent.id != uuid.UUID(agent_id),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Key already in use by another agent")

        old_key_id = agent.key_id
        agent.public_key = new_public_key
        agent.key_id = f"{new_did}#key-1"
        agent.updated_at = utcnow()

        # Invalidate old API keys
        from app.models.agent import ApiKey

        old_keys = await db.execute(select(ApiKey).where(ApiKey.agent_id == uuid.UUID(agent_id)))
        for key in old_keys.scalars().all():
            key.is_active = False

        # Generate new API key
        raw_api_key = generate_api_key()
        api_key = ApiKey(
            agent_id=agent.id,
            key_hash=hash_api_key(raw_api_key),
            key_prefix=raw_api_key[:12],
            is_active=True,
        )
        db.add(api_key)
        await db.flush()

        # Audit log
        await log_audit_event(
            db,
            event_type="key_rotated",
            actor_id=agent.id,
            target_id=agent.id,
            target_type="agent",
            payload={"old_key_id": old_key_id, "new_key_id": agent.key_id},
        )

        return {
            "agent_id": agent_id,
            "new_key_id": agent.key_id,
            "api_key": raw_api_key,
            "rotated_at": utcnow().isoformat(),
        }

    async def authenticate_api_key(self, db: AsyncSession, api_key: str) -> dict[str, Any] | None:
        key_hash = hash_api_key(api_key)
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active.is_(True),
            )
        )
        key_record = result.scalar_one_or_none()
        if not key_record:
            return None

        # Update last used
        key_record.last_used_at = utcnow()

        # Get agent
        agent_result = await db.execute(select(Agent).where(Agent.id == key_record.agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return None

        return self._agent_to_dict(agent)

    def _agent_to_dict(self, agent: Agent) -> dict[str, Any]:
        return {
            "agent_id": str(agent.id),
            "did": agent.did,
            "name": agent.name,
            "display_name": agent.display_name,
            "version": agent.version,
            "description": agent.description,
            "status": agent.status,
            "endpoint": agent.endpoint,
            "capabilities": agent.capabilities,
            "tags": agent.tags,
            "trust_score": None,
            "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "public_key": agent.public_key,
            "metadata": agent.metadata_,
        }
