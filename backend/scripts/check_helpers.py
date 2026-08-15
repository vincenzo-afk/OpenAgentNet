"""Shared helpers for the per-phase verification scripts.

The verification checks assert against a clean state, but repeated runs leave
orphan trust records, messages, and workflow runs behind. This module resets
all rows related to demo / e2e agents (by agent id) and clears the transient
tables so each check script starts from a deterministic baseline without
touching operator configuration.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0] + "/..")


# One shared event loop for the whole process: asyncpg attaches connections
# to the loop that first used them, so every coroutine must run on that
# same loop (asyncio.run would swap loops between calls).
_SHARED_LOOP: asyncio.AbstractEventLoop = asyncio.new_event_loop()


def _run_sync(coro):
    return _SHARED_LOOP.run_until_complete(coro)


def reset_check_state() -> None:
    """Delete demo/e2e-related rows and transient tables in one transaction."""
    from sqlalchemy import delete

    from app.core.database import get_session_factory
    from app.models.agent import Agent, ApiKey
    from app.models.audit import AuditEvent
    from app.models.marketplace import MarketplaceListing, MarketplaceUsage
    from app.models.memory import MemoryObject, MemoryPermission
    from app.models.negotiation import Negotiation
    from app.models.task import Task
    from app.models.trust import Dispute, Endorsement, TrustRecord
    from app.models.workflow import Workflow, WorkflowTask

    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as db:
            # Wipe FK-holding tables FIRST, then agents, so no foreign-key
            # violation is raised (nothing cascades; demo data is transient).
            for model in (
                ApiKey,
                TrustRecord,
                Endorsement,
                Dispute,
                Negotiation,
                WorkflowTask,
                Workflow,
                Task,
                MarketplaceListing,
                MarketplaceUsage,
                MemoryPermission,
                MemoryObject,
                AuditEvent,
            ):
                await db.execute(delete(model))
            await db.execute(
                delete(Agent).where(
                    Agent.name.in_(["demo-echo", "demo-summarizer"]),
                )
            )
            await db.commit()

    _run_sync(_run())


def reset_trust_state() -> None:
    """Wipe trust tables only — used after seeding demo traffic so that the
    check scripts start each assertion from a known-empty trust baseline."""
    from sqlalchemy import delete

    from app.core.database import get_session_factory
    from app.models.trust import Dispute, Endorsement, TrustRecord

    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as db:
            for model in (TrustRecord, Endorsement, Dispute):
                await db.execute(delete(model))
            await db.commit()

    _run_sync(_run())


if __name__ == "__main__":
    reset_check_state()
    print("check state reset")
