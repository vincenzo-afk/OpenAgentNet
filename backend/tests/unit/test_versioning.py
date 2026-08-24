from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.agent_version import AgentVersion
from app.schemas.versioning import AgentVersionDiffResponse
from app.services.registry import RegistryService


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _Session:
    def __init__(self, values):
        self.values = values

    async def execute(self, _query):
        return _Result(self.values)


@pytest.mark.asyncio
async def test_capability_diff_classifies_added_removed_and_changed() -> None:
    agent_id = uuid.uuid4()
    before = AgentVersion(
        agent_id=agent_id,
        revision=1,
        version="1.0.0",
        endpoint="https://one.example",
        capabilities=[{"name": "echo", "version": "1"}, {"name": "old", "version": "1"}],
        metadata_={"region": "local"},
    )
    after = AgentVersion(
        agent_id=agent_id,
        revision=2,
        version="2.0.0",
        endpoint="https://two.example",
        capabilities=[{"name": "echo", "version": "2"}, {"name": "new", "version": "1"}],
        metadata_={"region": "eu"},
    )

    result = await RegistryService().diff_versions(
        _Session([before, after]), str(agent_id), from_revision=1, to_revision=2
    )

    assert result["version_changed"] is True
    assert result["endpoint_changed"] is True
    assert result["metadata_changed"] is True
    assert {change["change"] for change in result["capabilities"]} == {"added", "removed", "changed"}


def test_version_diff_schema_rejects_unknown_change_type() -> None:
    with pytest.raises(ValidationError):
        AgentVersionDiffResponse(
            agent_id=str(uuid.uuid4()),
            from_revision=1,
            to_revision=2,
            version_changed=False,
            endpoint_changed=False,
            metadata_changed=False,
            capabilities=[{"name": "echo", "change": "unknown"}],
        )
