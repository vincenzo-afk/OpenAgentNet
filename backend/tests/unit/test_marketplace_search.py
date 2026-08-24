from __future__ import annotations

from sqlalchemy.dialects.postgresql import dialect

from app.services.marketplace import MarketplaceService


class _Rows:
    def scalar(self):
        return 0

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


async def test_search_compiles_all_documented_filters() -> None:
    db = _DB()
    result = await MarketplaceService().search_listings(
        db,
        capability="summarize",
        min_trust_score=0.75,
        min_price=0.001,
        max_price=0.01,
        max_latency_p95_ms=2500,
    )

    assert result["total"] == 0
    assert len(db.statements) == 2
    compiled_statements = [statement.compile(dialect=dialect()) for statement in db.statements]
    compiled = "\n".join(str(statement) for statement in compiled_statements)
    assert "trust_records" in compiled
    assert "agents" in compiled
    bind_values = {
        value
        for statement in compiled_statements
        for value in statement.params.values()
        if isinstance(value, (str, int, float))
    }
    assert {"p95_latency_ms", "latency_p95_ms", "amount", "price"}.issubset(bind_values)
