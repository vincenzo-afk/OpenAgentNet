from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agents import router as agents_router
from app.api.v1.common import router as common_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.federation import router as federation_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.memory import router as memory_router
from app.api.v1.messages import router as messages_router
from app.api.v1.messages import task_router as tasks_router
from app.api.v1.negotiations import router as negotiations_router
from app.api.v1.routing import router as routing_router
from app.api.v1.trust import router as trust_router
from app.api.v1.teams import router as teams_router
from app.api.v1.workflows import router as workflows_router
from app.core.config import get_settings
from app.core.database import close_connections
from app.core.nats_client import disconnect_nats
from app.core.observability import configure_json_logging, configure_tracing, metrics, observe_http
from app.core.rate_limit import PayloadSizeMiddleware, RateLimitMiddleware
from app.core.workers import start_background_workers

settings = get_settings()
configure_tracing()
configure_json_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_background_workers()
    yield
    await close_connections()
    await disconnect_nats()


app = FastAPI(
    title="OpenAgentNet",
    description="The protocol and infrastructure layer for AI agent networks",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Payload size enforcement (must be added after CORS)
app.add_middleware(PayloadSizeMiddleware)

# Rate limiting middleware (must be added after CORS and payload size)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    return await observe_http(request, call_next)

prefix = settings.api_v1_prefix

app.include_router(agents_router, prefix=prefix)
app.include_router(discovery_router, prefix=prefix)
app.include_router(federation_router, prefix=prefix)
app.include_router(messages_router, prefix=prefix)
app.include_router(tasks_router, prefix=prefix)
app.include_router(trust_router, prefix=prefix)
app.include_router(teams_router, prefix=prefix)
app.include_router(negotiations_router, prefix=prefix)
app.include_router(routing_router, prefix=prefix)
app.include_router(workflows_router, prefix=prefix)
app.include_router(memory_router, prefix=prefix)
app.include_router(marketplace_router, prefix=prefix)
app.include_router(privacy_router, prefix=prefix)
app.include_router(common_router, prefix=prefix)


@app.get("/metrics", include_in_schema=False, response_class=PlainTextResponse)
async def metrics_endpoint():
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


@app.get("/")
async def root():
    return {
        "name": "OpenAgentNet",
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/v1",
    }
