from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.registry import service as registry_module


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value


class _DB:
    def __init__(self, agent):
        self.results = [_Result(agent), _Result(2), _Result(0.91)]

    async def execute(self, _statement):
        return self.results.pop(0)

    async def flush(self):
        return None

    def add(self, _value):
        return None


@pytest.mark.asyncio
async def test_profile_update_preserves_persisted_trust_score(monkeypatch) -> None:
    agent_id = uuid.uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        did=f"did:oan:{agent_id}",
        name="agent",
        display_name="Agent",
        version="1.0.1",
        description=None,
        status="active",
        region="local",
        is_federated=False,
        origin_registry_id="local",
        endpoint="https://agent.example/execute",
        capabilities=[{"name": "summarize"}],
        tags=[],
        public_key="key",
        key_id="key-1",
        protocol_version="1.0",
        metadata_={},
        last_seen_at=None,
        created_at=None,
        updated_at=None,
    )
    captured = {}

    async def fake_sync(agent_id, capabilities, *, trust_score, active):
        captured.update(agent_id=agent_id, capabilities=capabilities, trust_score=trust_score, active=active)

    monkeypatch.setattr(registry_module, "sync_agent", fake_sync)
    result = await registry_module.RegistryService().update_agent(
        _DB(agent), str(agent_id), {"description": "updated"}
    )

    assert result["description"] == "updated"
    assert captured["trust_score"] == 0.91
    assert captured["active"] is True
