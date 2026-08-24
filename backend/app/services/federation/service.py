from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import (
    base64_to_public_key,
    generate_api_key,
    hash_api_key,
    public_key_to_bytes,
    verify_api_key,
)
from app.core.identifiers import build_did, derive_agent_id_from_bytes, parse_agent_id
from app.models.agent import Agent
from app.models.federation import FederatedRegistry
from app.schemas.federation import (
    AgentMigrationRequest,
    FederatedAgentRecord,
    RegistryPeerCreate,
    RegistrySyncRequest,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class FederationService:
    async def create_peer(
        self, db: AsyncSession, request: RegistryPeerCreate
    ) -> tuple[dict[str, Any], str]:
        existing = await db.execute(
            select(FederatedRegistry).where(FederatedRegistry.registry_id == request.registry_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Registry peer already exists")

        shared_secret = generate_api_key()
        peer = FederatedRegistry(
            registry_id=request.registry_id,
            name=request.name,
            endpoint=str(request.endpoint).rstrip("/"),
            region=request.region,
            shared_secret_hash=hash_api_key(shared_secret),
            metadata_=request.metadata,
        )
        db.add(peer)
        await db.flush()
        return self._peer_to_dict(peer), shared_secret

    async def list_peers(self, db: AsyncSession) -> list[dict[str, Any]]:
        result = await db.execute(
            select(FederatedRegistry).order_by(FederatedRegistry.region, FederatedRegistry.name)
        )
        return [self._peer_to_dict(peer) for peer in result.scalars().all()]

    async def authenticate_peer(
        self, db: AsyncSession, registry_id: str, token: str
    ) -> FederatedRegistry | None:
        result = await db.execute(
            select(FederatedRegistry).where(
                FederatedRegistry.registry_id == registry_id,
                FederatedRegistry.is_active.is_(True),
            )
        )
        peer = result.scalar_one_or_none()
        if not peer or not verify_api_key(token, peer.shared_secret_hash):
            return None
        return peer

    async def sync_registry(
        self, db: AsyncSession, peer: FederatedRegistry, request: RegistrySyncRequest
    ) -> dict[str, Any]:
        if request.source_registry_id != peer.registry_id:
            raise ValueError("source_registry_id does not match authenticated peer")

        accepted = rejected = removed = 0
        for record in request.agents:
            try:
                if await self._upsert_federated_agent(db, peer, record):
                    accepted += 1
                else:
                    rejected += 1
            except (ValueError, TypeError, UnicodeError):
                rejected += 1

        for raw_agent_id in request.removed_agent_ids:
            agent_id = parse_agent_id(raw_agent_id)
            if not agent_id:
                rejected += 1
                continue
            result = await db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.is_federated.is_(True),
                    Agent.origin_registry_id == peer.registry_id,
                )
            )
            agent = result.scalar_one_or_none()
            if agent:
                agent.deleted_at = utcnow()
                agent.status = "deregistered"
                removed += 1

        now = utcnow()
        peer.last_sync_at = now
        peer.last_sync_cursor = request.cursor or now.isoformat()
        await db.flush()
        return {
            "source_registry_id": peer.registry_id,
            "accepted": accepted,
            "removed": removed,
            "rejected": rejected,
            "next_cursor": peer.last_sync_cursor,
            "synced_at": now,
        }

    async def _upsert_federated_agent(
        self, db: AsyncSession, peer: FederatedRegistry, record: FederatedAgentRecord
    ) -> bool:
        public_key = base64_to_public_key(record.public_key)
        derived_id = derive_agent_id_from_bytes(public_key_to_bytes(public_key))
        parsed_id = parse_agent_id(record.agent_id)
        if not parsed_id or parsed_id != derived_id:
            raise ValueError("agent_id is not derived from public_key")
        if record.did != build_did(parsed_id):
            raise ValueError("DID does not match agent_id")
        if record.region != peer.region:
            raise ValueError("agent region does not match source registry region")

        result = await db.execute(select(Agent).where(Agent.id == parsed_id))
        agent = result.scalar_one_or_none()
        if agent and not agent.is_federated:
            # A local record is authoritative and must never be overwritten by a peer.
            return False
        if not agent:
            agent = Agent(
                id=parsed_id,
                did=record.did,
                name=record.name,
                version=record.version,
                owner_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{peer.registry_id}:{record.agent_id}"),
                owner_type="organization",
                public_key=record.public_key,
                key_id=f"{record.did}#key-1",
                protocol_version="0.1.0",
                endpoint=str(record.endpoint).rstrip("/"),
                is_federated=True,
                origin_registry_id=peer.registry_id,
            )
            db.add(agent)
        agent.name = record.name
        agent.display_name = record.display_name
        agent.version = record.version
        agent.description = record.description
        agent.status = record.status
        agent.region = record.region
        agent.endpoint = str(record.endpoint).rstrip("/")
        agent.health_endpoint = str(record.health_endpoint).rstrip("/") if record.health_endpoint else None
        agent.public_key = record.public_key
        agent.capabilities = record.capabilities
        agent.permissions_required = record.permissions_required
        agent.permissions_offered = record.permissions_offered
        agent.tags = record.tags
        agent.metadata_ = record.metadata
        agent.deleted_at = None
        agent.is_federated = True
        agent.origin_registry_id = peer.registry_id
        if record.updated_at:
            agent.updated_at = record.updated_at
        return True

    async def migrate_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        request: AgentMigrationRequest,
    ) -> dict[str, Any] | None:
        parsed = parse_agent_id(agent_id)
        if not parsed:
            return None
        result = await db.execute(select(Agent).where(Agent.id == parsed, Agent.deleted_at.is_(None)))
        agent = result.scalar_one_or_none()
        if not agent:
            return None
        previous_region = agent.region
        previous_registry = agent.origin_registry_id
        agent.region = request.target_region
        agent.origin_registry_id = request.target_registry_id
        agent.status = "active"
        agent.is_federated = request.target_registry_id != get_settings().registry_id
        agent.updated_at = utcnow()
        await db.flush()
        return {
            "agent_id": str(agent.id),
            "previous_region": previous_region,
            "region": agent.region,
            "previous_registry_id": previous_registry,
            "origin_registry_id": agent.origin_registry_id,
            "migrated_at": agent.updated_at,
        }

    @staticmethod
    def _peer_to_dict(peer: FederatedRegistry) -> dict[str, Any]:
        return {
            "registry_id": peer.registry_id,
            "name": peer.name,
            "endpoint": peer.endpoint,
            "region": peer.region,
            "is_active": peer.is_active,
            "last_sync_at": peer.last_sync_at,
            "last_sync_cursor": peer.last_sync_cursor,
            "metadata": peer.metadata_ or {},
            "created_at": peer.created_at,
            "updated_at": peer.updated_at,
        }
