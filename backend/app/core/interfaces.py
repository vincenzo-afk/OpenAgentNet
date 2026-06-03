from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class RegistryServiceProtocol(Protocol):
    async def register(self, db: AsyncSession, manifest: dict, proof: dict) -> dict[str, Any]: ...

    async def get_agent(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None: ...

    async def update_agent(
        self, db: AsyncSession, agent_id: str, updates: dict
    ) -> dict[str, Any]: ...

    async def deregister_agent(self, db: AsyncSession, agent_id: str) -> None: ...

    async def list_agents(
        self, db: AsyncSession, status: str | None, limit: int, offset: int
    ) -> dict[str, Any]: ...

    async def verify_signature(
        self, db: AsyncSession, agent_id: str, message: bytes, signature: str
    ) -> bool: ...


@runtime_checkable
class DiscoveryServiceProtocol(Protocol):
    async def search(
        self,
        db: AsyncSession,
        capabilities: list[str] | None = None,
        filters: dict | None = None,
        sort: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    async def get_similar(self, db: AsyncSession, agent_id: str, limit: int = 5) -> list[dict]: ...


@runtime_checkable
class MessagingServiceProtocol(Protocol):
    async def send_message(
        self, db: AsyncSession, envelope: dict, sender_id: str
    ) -> dict[str, Any]: ...

    async def get_message(
        self, db: AsyncSession, message_id: str, agent_id: str
    ) -> dict[str, Any] | None: ...

    async def list_messages(
        self,
        db: AsyncSession,
        agent_id: str,
        direction: str | None = None,
        message_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]: ...


@runtime_checkable
class TrustServiceProtocol(Protocol):
    async def get_trust_record(self, db: AsyncSession, agent_id: str) -> dict[str, Any] | None: ...

    async def record_outcome(
        self, db: AsyncSession, task_id: str, success: bool, execution_ms: int | None = None
    ) -> None: ...

    async def endorse(
        self,
        db: AsyncSession,
        from_agent_id: str,
        to_agent_id: str,
        capability: str,
        comment: str | None = None,
    ) -> dict[str, Any]: ...

    async def flag(
        self,
        db: AsyncSession,
        reported_agent_id: str,
        reporter_agent_id: str,
        reason: str,
        task_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_events(self, db: AsyncSession, agent_id: str, limit: int = 50) -> list[dict]: ...


@runtime_checkable
class NegotiationServiceProtocol(Protocol):
    async def create_proposal(
        self, db: AsyncSession, requester_id: str, target_id: str, proposal: dict
    ) -> dict[str, Any]: ...

    async def respond(
        self, db: AsyncSession, negotiation_id: str, response: dict
    ) -> dict[str, Any]: ...

    async def get_negotiation(
        self, db: AsyncSession, negotiation_id: str
    ) -> dict[str, Any] | None: ...


@runtime_checkable
class OrchestrationServiceProtocol(Protocol):
    async def create_workflow(
        self, db: AsyncSession, owner_agent_id: str, definition: dict, name: str
    ) -> dict[str, Any]: ...

    async def get_workflow(self, db: AsyncSession, workflow_id: str) -> dict[str, Any] | None: ...

    async def list_workflows(
        self, db: AsyncSession, agent_id: str, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]: ...


@runtime_checkable
class MemoryServiceProtocol(Protocol):
    async def write_memory(
        self,
        db: AsyncSession,
        owner_agent_id: str,
        namespace: str,
        key: str,
        data: dict,
        permissions: list[dict] | None = None,
        ephemeral: bool = False,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]: ...

    async def read_memory(
        self, db: AsyncSession, agent_id: str, memory_id: str
    ) -> dict[str, Any] | None: ...

    async def list_memory(
        self,
        db: AsyncSession,
        agent_id: str,
        namespace: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    async def delete_memory(self, db: AsyncSession, agent_id: str, memory_id: str) -> None: ...


@runtime_checkable
class MarketplaceServiceProtocol(Protocol):
    async def create_listing(
        self, db: AsyncSession, agent_id: str, listing: dict
    ) -> dict[str, Any]: ...

    async def get_listing(self, db: AsyncSession, listing_id: str) -> dict[str, Any] | None: ...

    async def search_listings(
        self,
        db: AsyncSession,
        capability: str | None = None,
        min_trust_score: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    async def update_listing(
        self, db: AsyncSession, agent_id: str, updates: dict
    ) -> dict[str, Any]: ...

    async def delete_listing(self, db: AsyncSession, agent_id: str) -> None: ...
