from __future__ import annotations

import uuid

import pytest
from sqlalchemy.dialects.postgresql import dialect

from app.services.discovery import DiscoveryService


class _Rows:
    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []


class _DB:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Rows()


async def test_discovery_supports_latency_filter_and_sort() -> None:
    db = _DB()
    result = await DiscoveryService().search(
        db,
        capabilities=["summarize"],
        filters={
            "min_trust_score": 0.7,
            "max_latency_p95_ms": 2500,
            "language": "en",
            "metadata": {"domain": "nlp"},
            "exclude": [str(uuid.uuid4())],
        },
        sort="latency_p95_ms:asc",
    )

    assert result["total"] == 0
    assert len(db.statements) == 2
    compiled = [statement.compile(dialect=dialect()) for statement in db.statements]
    sql = "\n".join(str(statement) for statement in compiled)
    assert "trust_records" in sql
    assert sql.count("JOIN trust_records") == 2  # one count query and one result query
    assert "agents.capabilities" in sql
    bind_values = {
        value
        for statement in compiled
        for value in statement.params.values()
        if isinstance(value, (str, int, float))
    }
    assert {"latency_p95_ms", "latency_estimate_ms", "language", "domain"}.issubset(bind_values)


@pytest.mark.asyncio
async def test_empty_capability_index_short_circuits_authoritative_query() -> None:
    async def empty_candidates(*_args, **_kwargs):
        return []

    import app.services.discovery.service as discovery_module

    original = discovery_module.candidate_ids
    discovery_module.candidate_ids = empty_candidates
    try:
        db = _DB()
        result = await DiscoveryService().search(db, capabilities=["missing-capability"])
    finally:
        discovery_module.candidate_ids = original

    assert result["total"] == 0
    assert result["agents"] == []
    assert len(db.statements) == 2
    sql = "\n".join(str(statement.compile(dialect=dialect())) for statement in db.statements)
    assert "agents.id IN" in sql


async def test_discovery_supports_cost_sort() -> None:
    db = _DB()
    await DiscoveryService().search(db, sort="cost:asc")
    compiled = db.statements[1].compile(dialect=dialect())
    assert "cost_estimate" in compiled.params.values()
    assert "value" in compiled.params.values()
