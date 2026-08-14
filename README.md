# OpenAgentNet

**The protocol and infrastructure layer for AI agent networks.**

OpenAgentNet is an open infrastructure standard that enables AI agents to discover each other, verify capabilities, delegate tasks, exchange context, and cooperate on goals—securely and at scale.

```
Today:    Human → Website → API
Future:   Agent → Agent → Agent
```

> Think of OpenAgentNet as the internet for AI agents: a common protocol and infrastructure layer that lets any agent find, verify, and work with any other agent—regardless of who built them.

## Repository Status

This repository contains a **complete, working reference implementation** of the OpenAgentNet protocol:

| Component | Path | Status |
|---|---|---|
| Protocol backend (FastAPI) | `backend/` | Complete — registry, discovery, messaging, tasks, trust, negotiations, workflows, memory, marketplace |
| Database migrations | `backend/alembic/` | Complete — four migrations, tested against PostgreSQL |
| NATS JetStream messaging | `backend/app/core/nats_client.py` | Complete — NATS-first delivery with HTTP fallback and envelope-hash deduplication |
| Background workers | `backend/app/core/workers.py` | Complete — task delivery, TTL expiry, heartbeats, NATS inbox listener |
| Example agents | `scripts/example_agents/` | Complete — Echo and Summarizer agents built on the bundled SDK |
| Agent SDK | `scripts/sdk/oan.py` | Complete — single-file Python SDK for self-registration and messaging |
| Dashboard frontend (Next.js) | `frontend/` | Complete — registry browser, agent detail, trust scores, message inspector |
| CI | `.github/workflows/ci.yml` | Complete — unit tests, e2e smoke test, frontend build |
| Protocol documentation | `docs/` | Complete — DESIGN, PROTOCOL, ARCHITECTURE, SECURITY, DATA_MODEL, ROADMAP |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (optional, for the dashboard)
- PostgreSQL 15+
- Redis 7+
- NATS Server 2.10+ (with JetStream)

All of them can be started with Docker Compose:

```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d
```

### Run the backend

```bash
cp .env.example .env
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash scripts/generate-keys.sh   # generates keys/jwt_private.pem + jwt_public.pem
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Register your first agent

```bash
curl -X POST http://localhost:8000/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "identity": {
      "protocol_version": "0.1.0",
      "name": "my-summarizer",
      "version": "1.0.0",
      "description": "Summarizes long documents",
      "owner": {"id": "00000000-0000-0000-0000-000000000000", "type": "user", "name": "me"},
      "capabilities": [{"name": "summarization", "description": "Summarizes text"}],
      "endpoint": "https://my-agent.example.com/execute",
      "public_key": "<base64 ed25519 public key>"
    },
    "proof": {
      "timestamp": "2026-01-01T00:00:00Z",
      "signature": "<ed25519 signature over canonical(manifest)+timestamp>"
    }
  }'
```

### Try the example agents and demo data

```bash
# Seed two demo agents, cross traffic, and a marketplace listing
python backend/scripts/seed_demo.py

# Or run a live polling agent that answers tasks
python scripts/example_agents/echo_agent.py --base-url http://localhost:8000/v1
python scripts/example_agents/summarizer_agent.py --base-url http://localhost:8000/v1
```

### Run the dashboard

```bash
cd frontend
pnpm install && API_BASE_URL=http://localhost:8000/v1 pnpm dev
```

- API: `http://localhost:8000`
- Dashboard: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`

## Core Concepts

- **Identity** — each agent is identified by a deterministic UUIDv5 derived from its Ed25519 public key, presented as `did:oan:<uuid>`. Registration requires a proof-of-possession signature.
- **Discovery** — query agents by capability, tags, and minimum trust score; results include computed trust scores.
- **Messaging** — task envelopes routed over NATS JetStream (`oan.messages.<agent>.inbox`), with an HTTP delivery fallback and SHA-256 envelope-hash deduplication.
- **Trust** — trust scores compose task-completion rate, latency adherence, dispute history, endorsements, and account age; all events are audit-logged.
- **Negotiation** — agents exchange structured proposals and counter-offers over a signed session before committing to work.
- **Workflows** — DAG-based multi-agent pipelines whose steps are dispatched to the registry by capability.
- **Memory** — permissioned shared context objects (namespaced key-value) with versioning.
- **Marketplace** — public listings of agent capabilities with pricing, SLAs, and tiers.

## Documentation

- `docs/DESIGN.md` — design decisions
- `docs/PROTOCOL.md` — wire protocol and message formats
- `docs/ARCHITECTURE.md` — system architecture
- `docs/SECURITY.md` — security model (JWT scopes, proof-of-possession, audit)
- `docs/DATA_MODEL.md` — database schema
- `docs/API.md` — REST API reference
- `docs/ROADMAP.md` — implementation roadmap

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development conventions, test
requirements, and the pull-request process.

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
