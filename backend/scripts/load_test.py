from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from typing import Sequence

import httpx


@dataclass(frozen=True)
class LoadTestResult:
    total_requests: int
    successful_requests: int
    failed_requests: int
    elapsed_seconds: float
    requests_per_minute: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * quantile))
    return ordered[min(len(ordered) - 1, rank - 1)]


async def run_load_test(
    base_url: str,
    path: str,
    *,
    requests: int,
    concurrency: int,
    timeout: float,
    token: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LoadTestResult:
    if requests <= 0 or concurrency <= 0:
        raise ValueError("requests and concurrency must be positive")
    concurrency = min(concurrency, requests)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    latencies: list[float] = []
    status_counts: dict[str, int] = {}
    next_request = 0
    lock = asyncio.Lock()
    started = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=timeout,
        transport=transport,
    ) as client:
        async def worker() -> None:
            nonlocal next_request
            while True:
                async with lock:
                    if next_request >= requests:
                        return
                    next_request += 1
                request_started = time.perf_counter()
                try:
                    response = await client.get(path)
                    status = str(response.status_code)
                except httpx.HTTPError:
                    status = "error"
                latencies.append((time.perf_counter() - request_started) * 1000)
                status_counts[status] = status_counts.get(status, 0) + 1

        await asyncio.gather(*(worker() for _ in range(concurrency)))

    elapsed = max(time.perf_counter() - started, 0.000001)
    successful = sum(value for key, value in status_counts.items() if key.startswith("2"))
    return LoadTestResult(
        total_requests=requests,
        successful_requests=successful,
        failed_requests=requests - successful,
        elapsed_seconds=elapsed,
        requests_per_minute=requests / elapsed * 60,
        p50_ms=percentile(latencies, 0.50),
        p95_ms=percentile(latencies, 0.95),
        p99_ms=percentile(latencies, 0.99),
        status_counts=status_counts,
    )


def evaluate_thresholds(
    result: LoadTestResult,
    *,
    max_p95_ms: float | None = None,
    max_p99_ms: float | None = None,
    min_requests_per_minute: float | None = None,
    min_success_rate: float | None = None,
) -> dict[str, object]:
    """Evaluate optional targets without implying they were measured in production."""
    success_rate = (
        result.successful_requests / result.total_requests * 100
        if result.total_requests
        else 0.0
    )
    checks: dict[str, bool] = {}
    if max_p95_ms is not None:
        checks["p95_ms"] = result.p95_ms <= max_p95_ms
    if max_p99_ms is not None:
        checks["p99_ms"] = result.p99_ms <= max_p99_ms
    if min_requests_per_minute is not None:
        checks["requests_per_minute"] = result.requests_per_minute >= min_requests_per_minute
    if min_success_rate is not None:
        checks["success_rate"] = success_rate >= min_success_rate
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "success_rate_percent": round(success_rate, 4),
        "targets": {
            "max_p95_ms": max_p95_ms,
            "max_p99_ms": max_p99_ms,
            "min_requests_per_minute": min_requests_per_minute,
            "min_success_rate": min_success_rate,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAgentNet asynchronous API load test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--path", default="/v1/health")
    parser.add_argument("--requests", type=int, default=10_000)
    parser.add_argument("--concurrency", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--token")
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--max-p99-ms", type=float)
    parser.add_argument("--min-requests-per-minute", type=float)
    parser.add_argument("--min-success-rate", type=float, choices=range(0, 101))
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = asyncio.run(
        run_load_test(
            args.base_url,
            args.path,
            requests=args.requests,
            concurrency=args.concurrency,
            timeout=args.timeout,
            token=args.token,
        )
    )
    assessment = evaluate_thresholds(
        result,
        max_p95_ms=args.max_p95_ms,
        max_p99_ms=args.max_p99_ms,
        min_requests_per_minute=args.min_requests_per_minute,
        min_success_rate=args.min_success_rate,
    )
    print(json.dumps({"result": result.to_dict(), "thresholds": assessment}, indent=2, sort_keys=True))
    if not assessment["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
