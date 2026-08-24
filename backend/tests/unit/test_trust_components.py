from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.trust.components import TrustComponent, TrustComponentRegistry
from app.services.trust.service import TrustService


def test_registry_registers_named_components() -> None:
    registry = TrustComponentRegistry()
    component = registry.register("quality", 0.2, lambda _record: 0.75, "Quality signal")
    assert component.name == "quality"
    assert registry.list()[0].description == "Quality signal"


def test_latency_adherence_is_bounded_and_neutral_without_target() -> None:
    service = TrustService()
    assert service._latency_adherence(100, 200) == 1.0
    assert service._latency_adherence(400, 200) == 0.5
    assert service._latency_adherence(100, None) == 0.5
    assert service._latency_adherence(None, 200) == 0.5


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDB:
    def __init__(self, value):
        self.value = value

    async def execute(self, _query):
        return _FakeResult(self.value)


@pytest.mark.asyncio
async def test_latency_target_prefers_task_constraint_then_capability_estimate() -> None:
    service = TrustService()
    constrained_task = SimpleNamespace(
        constraints={"max_latency_ms": 250},
        to_agent_id=uuid.uuid4(),
        capability_name="summarize",
    )
    assert await service._latency_target_ms(_FakeDB([]), constrained_task) == 250

    declared_task = SimpleNamespace(
        constraints={},
        to_agent_id=uuid.uuid4(),
        capability_name="summarize",
    )
    db = _FakeDB([{"name": "summarize", "latency_estimate_ms": 1500}])
    assert await service._latency_target_ms(db, declared_task) == 1500


def test_record_to_dict_uses_observed_latency_component() -> None:
    record = SimpleNamespace(
        agent_id="agent-1",
        trust_score=0.7,
        outcome_rate=0.8,
        endorsement_score=0.5,
        dispute_penalty=0.0,
        age_factor=0.4,
        component_scores={"latency_adherence": 0.625},
        total_tasks=4,
        successful_tasks=3,
        dispute_count=0,
        last_computed_at=None,
        created_at=None,
        updated_at=None,
    )
    assert TrustService()._record_to_dict(record)["components"]["latency_adherence"] == 0.625


def test_plugin_scores_are_clamped_and_recorded(monkeypatch) -> None:
    components = [TrustComponent("quality", 1.0, lambda _record: 2.0)]
    monkeypatch.setattr("app.services.trust.service.get_trust_components", lambda: components)
    record = SimpleNamespace(
        created_at=None,
        outcome_rate=0.5,
        age_factor=0.1,
        dispute_penalty=0.0,
        component_scores={},
    )

    score = TrustService()._compute_trust_score(record)

    assert score == 1.0
    assert record.component_scores == {"quality": 1.0}
