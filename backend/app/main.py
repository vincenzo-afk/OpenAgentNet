from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agents import router as agents_router
from app.api.v1.common import router as common_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.memory import router as memory_router
from app.api.v1.messages import router as messages_router
from app.api.v1.messages import task_router as tasks_router
from app.api.v1.negotiations import router as negotiations_router
from app.api.v1.trust import router as trust_router
from app.api.v1.workflows import router as workflows_router
from app.core.config import get_settings
from app.core.database import close_connections
from app.core.rate_limit import PayloadSizeMiddleware, RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_connections()


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

prefix = settings.api_v1_prefix

app.include_router(agents_router, prefix=prefix)
app.include_router(discovery_router, prefix=prefix)
app.include_router(messages_router, prefix=prefix)
app.include_router(tasks_router, prefix=prefix)
app.include_router(trust_router, prefix=prefix)
app.include_router(negotiations_router, prefix=prefix)
app.include_router(workflows_router, prefix=prefix)
app.include_router(memory_router, prefix=prefix)
app.include_router(marketplace_router, prefix=prefix)
app.include_router(common_router, prefix=prefix)


@app.get("/")
async def root():
    return {
        "name": "OpenAgentNet",
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/v1",
    }
