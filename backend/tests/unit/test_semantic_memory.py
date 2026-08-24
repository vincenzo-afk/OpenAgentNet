from __future__ import annotations

import uuid

import pytest
from sqlalchemy.dialects.postgresql import dialect

from app.services.memory import MemoryService


class _Result:
    def __init__(self, rows=None, total=0):
        self.rows = rows or []
        self.total = total

    def scalar(self):
        return self.total

    def all(self):
        return self.rows


class _DB:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result()


@pytest.mark.asyncio
async def test_semantic_search_compiles_cosine_query_with_namespace() -> None:
    db = _DB()
    owner = uuid.uuid4()
    result = await MemoryService().search_memory(
        db,
        str(owner),
        [0.0] * 1536,
        namespace="agent:namespace",
        limit=5,
    )

    assert result == {"total": 0, "limit": 5, "offset": 0, "items": []}
    assert len(db.statements) == 2
    compiled = db.statements[1].compile(dialect=dialect())
    assert "memory_objects.embedding" in str(compiled)
    assert "cosine" not in str(compiled).lower()
    assert len(next(value for value in compiled.params.values() if isinstance(value, list))) == 1536


@pytest.mark.asyncio
async def test_semantic_search_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="1536 dimensions"):
        await MemoryService().search_memory(None, str(uuid.uuid4()), [0.0] * 3)


@pytest.mark.asyncio
async def test_memory_write_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="1536 dimensions"):
        await MemoryService().write_memory(
            None,
            str(uuid.uuid4()),
            "agent:namespace",
            "key",
            {"value": "x"},
            embedding=[0.0] * 3,
        )
