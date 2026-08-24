from __future__ import annotations

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
        filters={"min_trust_score": 0.7, "max_latency_p95_ms": 2500},
        sort="latency_p95_ms:asc",
    )

    assert result["total"] == 0
    assert len(db.statements) == 2
    compiled = [statement.compile(dialect=dialect()) for statement in db.statements]
    sql = "\n".join(str(statement) for statement in compiled)
    assert "trust_records" in sql
    assert "agents.capabilities" in sql
    bind_values = {
        value
        for statement in compiled
        for value in statement.params.values()
        if isinstance(value, (str, int, float))
    }
    assert {"latency_p95_ms", "latency_estimate_ms"}.issubset(bind_values)
