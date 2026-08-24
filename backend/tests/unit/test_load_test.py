from __future__ import annotations

import pytest
from httpx import ASGITransport

from scripts.load_test import percentile, run_load_test


def test_percentile_handles_empty_and_sorted_samples() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([30.0, 10.0, 20.0], 0.50) == 20.0
    assert percentile([10.0, 20.0, 30.0], 0.99) == 30.0


@pytest.mark.asyncio
async def test_load_test_aggregates_statuses_and_latency() -> None:
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/v1/health")
    async def health():
        return {"status": "ok"}

    result = await run_load_test(
        "http://testserver",
        "/v1/health",
        requests=6,
        concurrency=3,
        timeout=1.0,
        transport=ASGITransport(app=app),
    )

    assert result.total_requests == 6
    assert result.successful_requests == 6
    assert result.failed_requests == 0
    assert result.status_counts == {"200": 6}


@pytest.mark.asyncio
async def test_load_test_rejects_non_positive_inputs() -> None:
    with pytest.raises(ValueError, match="positive"):
        await run_load_test("http://testserver", "/v1/health", requests=0, concurrency=1, timeout=1)
