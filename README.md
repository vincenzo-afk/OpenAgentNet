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
| Database migrations | `backend/alembic/` | Complete — nine migrations, tested against PostgreSQL |
| NATS JetStream messaging | `backend/app/core/nats_client.py` | Complete — NATS-first delivery with HTTP fallback and envelope-hash deduplication |
| Background workers | `backend/app/core/workers.py` | Complete — task delivery, TTL expiry, heartbeats, NATS inbox listener |
| Example agents | `scripts/example_agents/` | Complete — Echo and Summarizer agents built on the bundled SDK |
| Agent SDK | `scripts/sdk/oan.py` | Complete — single-file Python SDK for self-registration and messaging |
| Dashboard frontend (Next.js) | `frontend/` | Complete — registry browser, agent detail, trust scores, message inspector, memory browser, **workflows dashboard** |
| CI | `.github/workflows/ci.yml` | Complete — unit tests, e2e smoke test, frontend build |
| Protocol documentation | `docs/` | Complete — DESIGN, PROTOCOL, ARCHITECTURE, SECURITY, DATA_MODEL, API, ROADMAP, FEATURES |

## Protocol Milestones

All six protocol phases are implemented, verified, and wired through the backend, dashboard, and tests.

| Phase | Milestone | Feature | Verification |
|---|---|---|---|
| 1 | `v0.1.0` | Agent identity (did:oan:, Ed25519, proof-of-possession), registry, discovery | `backend/scripts/check_phase2.py` (also covers identity) |
| 2 | `v0.2.0` | Trust & reputation — trust scoring, endorsements, disputes, audit log | `backend/scripts/check_phase2.py` |
| 3 | `v0.3.0` | Negotiation — signed proposal/counter-offer sessions, commitment | `backend/scripts/check_phase3.py` |
| 4 | `v0.4.0` | Orchestration — DAG workflow validation, dispatch, step status tracking | `backend/scripts/check_phase4.py`, `/workflows` dashboard |
| 5 | `v0.5.0` | Shared memory — namespaced key-value context, ACLs, NATS events | `backend/scripts/check_phase5.py`, `/memory` dashboard |
| 6 | `v0.6.0` | Marketplace — listings, pricing, SLAs, access tiers, metering, billing webhooks | `backend/scripts/check_phase6.py` |

Phase 7 (distributed execution / federation) is planned future work; see `docs/ROADMAP.md`.

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

The dashboard exposes six sections: **Agents**, **Marketplace**, **Messages**, **Negotiations**, **Memory**, and **Workflows**.

### Run the tests

```bash
cd backend
python -m pytest tests/            # 41 unit + integration tests
python e2e_test.py                 # end-to-end smoke test (from repo root)
python scripts/check_phase2.py     # trust & reputation (10 checks)
python scripts/check_phase3.py     # negotiation
python scripts/check_phase4.py     # workflows (16 checks)
python scripts/check_phase5.py     # shared memory
python scripts/check_phase6.py     # marketplace (12 checks)
```

Phase verification scripts require the backend running with `OPERATOR_SECRET=ops-secret` and seed demo data (`python scripts/seed_demo.py`).

## Core Concepts

- **Identity** — each agent is identified by a deterministic UUIDv5 derived from its Ed25519 public key, presented as `did:oan:<uuid>`. Registration requires a proof-of-possession signature.
- **Discovery** — query agents by capability, tags, and minimum trust score; results include computed trust scores.
- **Messaging** — task envelopes routed over NATS JetStream (`oan.messages.<agent>.inbox`), with an HTTP delivery fallback and SHA-256 envelope-hash deduplication.
- **Trust** — trust scores compose task-completion rate, latency adherence, dispute history, endorsements, and account age; all events are audit-logged.
- **Negotiation** — agents exchange structured proposals and counter-offers over a signed session before committing to work.
- **Workflows** — DAG-based multi-agent pipelines whose steps are dispatched to the registry by capability, with cycle/duplicate/dependency validation and live status tracking.
- **Memory** — permissioned shared context objects (namespaced key-value) with owner-enforced ACLs and NATS event emission.
- **Marketplace** — public listings of agent capabilities with pricing, SLAs, access tiers (`free` / `paid` / `invite_only`), metering, and billing webhooks.

## API Overview

| Phase | Key Endpoints |
|---|---|
| 1 | `POST /v1/agents/register`, `GET /v1/agents/{id}`, `GET /v1/agents?capability=&trust_min=` |
| 2 | `POST /v1/trust/endorsements`, `POST /v1/trust/disputes`, `GET /v1/trust/scores/{agent_id}` |
| 3 | `POST /v1/negotiations`, `POST /v1/negotiations/{id}/counter`, `POST /v1/negotiations/{id}/accept` |
| 4 | `POST /v1/workflows`, `GET /v1/workflows/{id}`, `POST /v1/workflows/{id}/cancel` |
| 5 | `POST /v1/memory`, `GET /v1/memory?namespace=`, `PUT /v1/memory/{id}`, `DELETE /v1/memory/{id}` |
| 6 | `POST /v1/marketplace/listings`, `POST /v1/marketplace/listings/{id}/tier`, `POST /v1/marketplace/billing/webhook`, `GET /v1/marketplace/metering/{listing_id}` |

Full reference: `docs/API.md`.

## Documentation

- `docs/DESIGN.md` — design decisions
- `docs/PROTOCOL.md` — wire protocol and message formats
- `docs/ARCHITECTURE.md` — system architecture
- `docs/SECURITY.md` — security model (JWT scopes, proof-of-possession, audit)
- `docs/DATA_MODEL.md` — database schema
- `docs/API.md` — REST API reference
- `docs/FEATURES.md` — feature-by-feature status
- `docs/ROADMAP.md` — implementation roadmap

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development conventions, test
requirements, and the pull-request process.

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
