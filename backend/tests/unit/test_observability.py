from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from app.core.observability import JsonFormatter, MetricsRegistry, observe_http, request_id


def test_json_formatter_emits_structured_fields() -> None:
    import logging

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello"


def test_metrics_registry_renders_prometheus_counters() -> None:
    registry = MetricsRegistry()
    registry.observe_request("GET", "/health", 200, 0.125)
    output = registry.render()
    assert "openagentnet_http_requests_total" in output
    assert 'method="GET"' in output
    assert "openagentnet_http_request_duration_seconds_sum" in output


def test_request_id_reuses_provided_value() -> None:
    assert request_id("request-1") == "request-1"
    assert len(request_id(None)) > 10


@pytest.mark.asyncio
async def test_observability_middleware_sets_request_id_and_metrics() -> None:
    from app.core.observability import metrics

    request = SimpleNamespace(
        headers={},
        method="GET",
        scope={"route": SimpleNamespace(path="/health")},
        url=SimpleNamespace(path="/health"),
    )

    async def call_next(_request):
        return Response("ok", status_code=200)

    response = await observe_http(request, call_next)
    assert response.headers["X-Request-ID"]
    assert any(key[0] == "GET" and key[1] == "/health" for key in metrics.request_count)
