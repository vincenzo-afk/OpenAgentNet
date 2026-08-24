from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover - optional local fallback
    trace = None  # type: ignore[assignment]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


class MetricsRegistry:
    def __init__(self) -> None:
        self.request_count: dict[tuple[str, str, str], int] = defaultdict(int)
        self.request_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.request_duration_count: dict[tuple[str, str], int] = defaultdict(int)

    def observe_request(self, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        key = (method, route, str(status_code))
        self.request_count[key] += 1
        duration_key = (method, route)
        self.request_duration_sum[duration_key] += duration_seconds
        self.request_duration_count[duration_key] += 1

    @staticmethod
    def _labels(**labels: str) -> str:
        escaped = {key: value.replace('\\', '\\\\').replace('"', '\\"') for key, value in labels.items()}
        return ",".join(f'{key}="{value}"' for key, value in escaped.items())

    def render(self) -> str:
        lines = [
            "# HELP openagentnet_http_requests_total HTTP requests received by route and status.",
            "# TYPE openagentnet_http_requests_total counter",
        ]
        for (method, route, status), count in sorted(self.request_count.items()):
            labels = self._labels(method=method, route=route, status=status)
            lines.append(f"openagentnet_http_requests_total{{{labels}}} {count}")
        lines.extend([
            "# HELP openagentnet_http_request_duration_seconds_sum Total HTTP request duration in seconds.",
            "# TYPE openagentnet_http_request_duration_seconds summary",
        ])
        for (method, route), total in sorted(self.request_duration_sum.items()):
            labels = self._labels(method=method, route=route)
            count = self.request_duration_count[(method, route)]
            lines.append(f"openagentnet_http_request_duration_seconds_sum{{{labels}}} {total:.9f}")
            lines.append(f"openagentnet_http_request_duration_seconds_count{{{labels}}} {count}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()


def configure_tracing() -> None:
    """Configure an SDK tracer only when an exporter is explicitly enabled."""
    if trace is None:
        return
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    except ImportError:  # pragma: no cover - optional deployment dependency
        return

    provider = trace.get_tracer_provider()
    if provider.__class__.__name__ != "ProxyTracerProvider":
        return

    settings = get_settings()
    sdk_provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    exporter_name = (settings.otel_traces_exporter or "").lower()
    if exporter_name in {"otlp", "otlp_http"} and settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint}/v1/traces"
            sdk_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
        except ImportError:
            logging.getLogger(__name__).warning(
                "OTLP exporter requested but opentelemetry-exporter-otlp-proto-http is unavailable"
            )
    elif exporter_name == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        sdk_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(sdk_provider)


def configure_json_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None):
    if trace is None:
        yield None
        return
    tracer = trace.get_tracer("openagentnet")
    with tracer.start_as_current_span(name, attributes=attributes or {}) as current:
        yield current


def request_id(value: str | None) -> str:
    return value or str(uuid.uuid4())


async def observe_http(request: Any, call_next: Callable[..., Any]) -> Any:
    started = time.perf_counter()
    rid = request_id(request.headers.get("X-Request-ID"))
    with span("http.server", {"http.request.method": request.method, "http.request.id": rid}):
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            metrics.observe_request(request.method, route, status_code, time.perf_counter() - started)
    response.headers["X-Request-ID"] = rid
    return response
