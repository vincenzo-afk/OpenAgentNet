from __future__ import annotations

from types import SimpleNamespace

from app.services.trust.components import TrustComponent, TrustComponentRegistry
from app.services.trust.service import TrustService


def test_registry_registers_named_components() -> None:
    registry = TrustComponentRegistry()
    component = registry.register("quality", 0.2, lambda _record: 0.75, "Quality signal")
    assert component.name == "quality"
    assert registry.list()[0].description == "Quality signal"


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
