from __future__ import annotations

import pytest
from httpx import ASGITransport

from scripts.load_test import LoadTestResult, evaluate_thresholds, percentile, run_load_test


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


def test_load_test_evaluates_optional_nfr_thresholds() -> None:
    result = LoadTestResult(
        total_requests=100,
        successful_requests=99,
        failed_requests=1,
        elapsed_seconds=1.0,
        requests_per_minute=6000.0,
        p50_ms=20.0,
        p95_ms=80.0,
        p99_ms=120.0,
        status_counts={"200": 99, "500": 1},
    )
    assessment = evaluate_thresholds(
        result,
        max_p95_ms=100.0,
        max_p99_ms=150.0,
        min_requests_per_minute=5000.0,
        min_success_rate=99.0,
    )
    assert assessment["passed"] is True
    assert assessment["success_rate_percent"] == 99.0
    failed = evaluate_thresholds(result, max_p95_ms=50.0)
    assert failed["passed"] is False
    assert failed["checks"] == {"p95_ms": False}


@pytest.mark.asyncio
async def test_load_test_rejects_non_positive_inputs() -> None:
    with pytest.raises(ValueError, match="positive"):
        await run_load_test("http://testserver", "/v1/health", requests=0, concurrency=1, timeout=1)
