from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.task import TaskStreamChunkRequest


def test_stream_chunk_accepts_zero_and_final_marker() -> None:
    chunk = TaskStreamChunkRequest(sequence=0, chunk={"text": "hello"}, is_final=True)
    assert chunk.sequence == 0
    assert chunk.chunk == {"text": "hello"}
    assert chunk.is_final is True


def test_stream_chunk_rejects_negative_sequence() -> None:
    with pytest.raises(ValidationError):
        TaskStreamChunkRequest(sequence=-1, chunk={"text": "invalid"})


def test_stream_chunk_requires_object_payload() -> None:
    with pytest.raises(ValidationError):
        TaskStreamChunkRequest(sequence=1, chunk=["not", "an", "object"])
