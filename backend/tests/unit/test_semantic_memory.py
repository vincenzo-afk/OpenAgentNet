from __future__ import annotations

import uuid
from types import SimpleNamespace

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


class _UpdateDB:
    def __init__(self, memory):
        self.memory = memory

    async def execute(self, _statement):
        return _MemoryResult(self.memory)

    async def flush(self):
        return None

    async def commit(self):
        return None


class _MemoryResult:
    def __init__(self, memory):
        self.memory = memory

    def scalar_one_or_none(self):
        return self.memory


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
async def test_memory_update_replaces_supplied_embedding() -> None:
    owner = uuid.uuid4()
    memory = SimpleNamespace(
        id=uuid.uuid4(),
        namespace="agent:namespace",
        key="key",
        owner_agent_id=owner,
        data={"value": "old"},
        data_type="json",
        is_ephemeral=False,
        version=1,
        created_at=None,
        updated_at=None,
        embedding=[0.1] * 1536,
    )
    replacement = [0.2] * 1536
    result = await MemoryService().update_memory(
        _UpdateDB(memory), str(owner), str(memory.id), data={"value": "new"}, embedding=replacement
    )

    assert memory.embedding == replacement
    assert result["data"] == {"value": "new"}
    assert memory.version == 2


@pytest.mark.asyncio
async def test_memory_update_preserves_embedding_when_omitted() -> None:
    owner = uuid.uuid4()
    existing_embedding = [0.3] * 1536
    memory = SimpleNamespace(
        id=uuid.uuid4(),
        namespace="agent:namespace",
        key="key",
        owner_agent_id=owner,
        data={},
        data_type="json",
        is_ephemeral=False,
        version=1,
        created_at=None,
        updated_at=None,
        embedding=existing_embedding,
    )
    await MemoryService().update_memory(_UpdateDB(memory), str(owner), str(memory.id), data={"v": 1})
    assert memory.embedding == existing_embedding


@pytest.mark.asyncio
async def test_memory_update_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="1536 dimensions"):
        await MemoryService().update_memory(
            None, str(uuid.uuid4()), str(uuid.uuid4()), embedding=[0.0] * 3
        )


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
