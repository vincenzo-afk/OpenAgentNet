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
    generate_api_key,
    hash_api_key,
    public_key_to_bytes,
    verify_signature,
)
from app.core.config import get_settings
from app.core.identifiers import build_did, derive_agent_id_from_bytes, parse_agent_id
from app.core.security import create_access_token
from app.models.agent import Agent, ApiKey
from app.models.agent_version import AgentVersion
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

        # Compute deterministic agent_id from public key (per DESIGN.md).
        # The identity is a UUIDv5 derived from base58(sha256(pubkey))[:24],
        # so agents can compute their own ID offline while the PK column
        # remains a valid PostgreSQL UUID for all FK relations.
        agent_id = derive_agent_id_from_bytes(pk_bytes)
        did = build_did(agent_id)
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
                (Agent.id == agent_id) | (Agent.public_key == manifest.public_key)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent with this public key already registered")

        agent = Agent(
            id=agent_id,
            did=did,
            name=manifest.name,
            display_name=manifest.display_name,
            version=manifest.version,
            description=manifest.description,
            owner_id=uuid.UUID(manifest.owner.get("id", str(uuid.uuid4()))),
            owner_type=manifest.owner.get("type", "user"),
            status="active",
            region=(manifest.metadata or {}).get("region") or get_settings().region,
            is_federated=False,
            origin_registry_id=get_settings().registry_id,
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
        await self._record_version(db, agent)

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
            extra_claims={"agent_id": str(agent_id)},
        )

        return {
            "agent_id": str(agent_id),
            "did": did,
            "api_token": token,
            "registered_at": utcnow(),
            "status": "active",
        }

    async def get_agent(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None:
        resolved = parse_agent_id(agent_id)
        query = Agent.deleted_at.is_(None)
        if resolved:
            query = query & (Agent.id == resolved)
        else:
            query = query & (Agent.did.like(f"%{agent_id}%"))
        result = await db.execute(select(Agent).where(query))
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
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Agent not found")
        result = await db.execute(
            select(Agent).where(
                Agent.id == resolved,
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
        await self._record_version(db, agent)
        return self._agent_to_dict(agent)

    async def list_versions(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> dict[str, Any]:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Agent not found")
        result = await db.execute(
            select(AgentVersion)
            .where(AgentVersion.agent_id == resolved)
            .order_by(AgentVersion.revision.desc())
            .limit(limit)
        )
        versions = result.scalars().all()
        return {
            "agent_id": str(resolved),
            "total": len(versions),
            "items": [self._version_to_dict(version) for version in versions],
        }

    async def diff_versions(
        self, db: AsyncSession, agent_id: str, from_revision: int, to_revision: int
    ) -> dict[str, Any]:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Agent not found")
        result = await db.execute(
            select(AgentVersion).where(
                AgentVersion.agent_id == resolved,
                AgentVersion.revision.in_([from_revision, to_revision]),
            )
        )
        versions = {version.revision: version for version in result.scalars().all()}
        before = versions.get(from_revision)
        after = versions.get(to_revision)
        if not before or not after:
            raise ValueError("Requested agent revisions were not found")

        before_caps = {item.get("name", ""): item for item in before.capabilities}
        after_caps = {item.get("name", ""): item for item in after.capabilities}
        changes: list[dict[str, Any]] = []
        for name in sorted(set(before_caps) | set(after_caps)):
            if name not in before_caps:
                changes.append({"name": name, "change": "added", "after": after_caps[name]})
            elif name not in after_caps:
                changes.append({"name": name, "change": "removed", "before": before_caps[name]})
            elif before_caps[name] != after_caps[name]:
                changes.append(
                    {
                        "name": name,
                        "change": "changed",
                        "before": before_caps[name],
                        "after": after_caps[name],
                    }
                )
        return {
            "agent_id": str(resolved),
            "from_revision": from_revision,
            "to_revision": to_revision,
            "version_changed": before.version != after.version,
            "endpoint_changed": before.endpoint != after.endpoint,
            "metadata_changed": before.metadata_ != after.metadata_,
            "capabilities": changes,
        }

    async def _record_version(self, db: AsyncSession, agent: Agent) -> AgentVersion:
        latest_result = await db.execute(
            select(func.max(AgentVersion.revision)).where(AgentVersion.agent_id == agent.id)
        )
        latest = latest_result.scalar() or 0
        version = AgentVersion(
            agent_id=agent.id,
            revision=int(latest) + 1,
            version=agent.version,
            endpoint=agent.endpoint,
            capabilities=agent.capabilities or [],
            metadata_=agent.metadata_ or {},
        )
        db.add(version)
        await db.flush()
        return version

    def _version_to_dict(self, version: AgentVersion) -> dict[str, Any]:
        return {
            "agent_id": str(version.agent_id),
            "revision": version.revision,
            "version": version.version,
            "endpoint": version.endpoint,
            "capabilities": version.capabilities or [],
            "metadata": version.metadata_ or {},
            "created_at": version.created_at,
        }

    async def deregister_agent(
        self, db: AsyncSession, agent_id: str
    ) -> None:
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Agent not found")
        result = await db.execute(select(Agent).where(Agent.id == resolved))
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
        resolved = parse_agent_id(agent_id)
        if not resolved:
            raise ValueError("Agent not found")
        result = await db.execute(
            select(Agent).where(
                Agent.id == resolved,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:

            raise ValueError("Agent not found")

        new_pk = base64_to_public_key(new_public_key)
        new_pk_bytes = public_key_to_bytes(new_pk)
        new_did = build_did(derive_agent_id_from_bytes(new_pk_bytes))

        # Check no other agent uses this key
        existing = await db.execute(
            select(Agent).where(
                Agent.public_key == new_public_key,
                Agent.id != (resolved or uuid.UUID(agent_id)),
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

        old_keys = await db.execute(
            select(ApiKey).where(ApiKey.agent_id == (resolved or uuid.UUID(agent_id)))
        )
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
            "region": agent.region,
            "is_federated": agent.is_federated,
            "origin_registry_id": agent.origin_registry_id,
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
