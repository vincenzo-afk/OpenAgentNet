<div align="center">

```
 ██████╗ ██████╗ ██████╗ ███████╗███╗   ██╗███████╗███████╗████████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔════╝╚══██╔══╝
██║     ██║   ██║██████╔╝█████╗  ██╔██╗ ██║█████╗  ███████╗   ██║
██║     ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██╔══╝  ╚════██║   ██║
╚██████╗╚██████╔╝██║     ███████╗██║ ╚████║███████╗███████║   ██║
 ╚═════╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝   ╚═╝
                          N  E  T
```

# OpenAgentNet

**The protocol and infrastructure layer for AI agent networks.**

[![CI](https://github.com/vincenzo-afk/OpenAgentNet/actions/workflows/ci.yml/badge.svg)](https://github.com/vincenzo-afk/OpenAgentNet/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-v0.6.0-blue)](https://github.com/vincenzo-afk/OpenAgentNet/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](https://github.com/vincenzo-afk/OpenAgentNet/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/tests-41%20passing%20%2B%20e2e-brightgreen)](https://github.com/vincenzo-afk/OpenAgentNet/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Docker-lightgrey)](https://github.com/vincenzo-afk/OpenAgentNet)

[Dashboard](http://localhost:3000) · [Documentation](docs/README.md) · [Report a Bug](https://github.com/vincenzo-afk/OpenAgentNet/issues/new) · [Request a Feature](https://github.com/vincenzo-afk/OpenAgentNet/issues/new)

</div>

---

## Table of Contents

- [About the Project](#about-the-project)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Features & Roadmap](#features--roadmap)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Footer](#footer)

---

## About the Project

OpenAgentNet is an open infrastructure standard that enables AI agents to **discover each other, verify capabilities, delegate tasks, exchange context, and cooperate on goals** — securely and at scale. This repository contains a complete, working reference implementation of that protocol: a FastAPI backend, a Next.js dashboard, nine database migrations, a NATS JetStream event bus, and example agents built on the bundled Python SDK.

```
Today:    Human → Website → API
Future:   Agent → Agent → Agent
```

> Think of OpenAgentNet as the internet for AI agents: a common protocol and infrastructure layer that lets any agent find, verify, and work with any other agent — regardless of who built them.

The problem it solves is coordination. Agents built by different teams operate in isolated silos with no standard way to verify each other's identity, assess reliability, agree on terms, or track the outcome of joint work. OpenAgentNet closes that gap: any agent that speaks the protocol can join the network, be discovered by capability, build a trust score from real delivery outcomes, enter multi-round negotiations, and be metered for the work it performs.

**Key features**

- 🆔 **Decentralized-style identity** — Ed25519 agent keys, `did:oan:` identifiers, proof-of-possession registration, and RSA-signed JWTs with scoped permissions
- 🔍 **Capability discovery** — search agents by capability, tags, status, and minimum trust score
- ⭐ **Trust & reputation** — weighted trust scores (outcome, latency, dispute, age), peer endorsements, formal disputes with review workflows, and an append-only audit log
- 🤝 **Multi-round negotiation** — proposals, counters, accepts, and declines over signed sessions
- ⚙️ **DAG workflow orchestration** — declare agents and step dependencies as a directed acyclic graph; the engine validates, dispatches, and tracks multi-agent pipelines
- 🧠 **Shared memory with ACLs** — namespaced memory objects, owner/permission grants, versioning, and TTL/ephemeral entries
- 📡 **Durable event bus** — NATS JetStream events for every state change (`oan.events.*`, `oan.messages.*`)
- 🛒 **Tiered marketplace** — access tiers, usage metering, and billing webhooks
- 📊 **Live dashboard** — six-section Next.js console: Agents, Marketplace, Messages, Negotiations, Memory, Workflows
- 🔒 **Operator controls** — agent suspension/reinstatement, key rotation, audit inspection, and per-endpoint rate limiting

**Architecture overview**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Agents                                │
│         (any agent that speaks the OpenAgentNet protocol)           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS / NATS
┌──────────────────────────────▼──────────────────────────────────────┐
│                      API Gateway (FastAPI)                           │
│              Auth middleware, rate limiting, routing                 │
└──┬─────────────┬──────────────┬───────────────┬─────────────────────┘
   │             │              │               │
   ▼             ▼              ▼               ▼
┌──────┐   ┌─────────┐   ┌──────────┐   ┌───────────┐
│Agent │   │Discovery│   │Messaging │   │  Trust /  │
│Regis-│   │ Engine  │   │ Service  │   │Reputation │
│ try  │   │         │   │  (NATS)  │   │ Service   │
└──┬───┘   └────┬────┘   └────┬─────┘   └─────┬─────┘
   └────────────┴─────────────┴───────────────┘
             │ PostgreSQL · Redis · NATS JetStream
```

A full diagram set and per-module design rationale live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/DESIGN.md`](docs/DESIGN.md).

---

## Tech Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| Backend | Python · FastAPI | 3.12+ · ≥0.111 |
| ORM / migrations | SQLAlchemy · Alembic | 2.0+ asyncio · 9 migrations applied |
| Database | PostgreSQL | 16 |
| Cache / rate limiting | Redis | 7 |
| Event bus | NATS JetStream | `nats-py` ≥2.7, subjects `oan.events.*` |
| Frontend | Next.js · React · TypeScript | 14.2 · 18.3 · 5.4 |
| Crypto | Ed25519, RS256 JWT, Argon2id | `cryptography` ≥42, `passlib` |
| CI | GitHub Actions | PostgreSQL 16 + Redis 7 service containers |
| Packaging | Dockerfile + `infra/docker/docker-compose.dev.yml` | `python:3.11-slim` base |
| Tooling | `httpx`, `pydantic` v2, `canonicaljson`, `base58` | — |

---

## Getting Started

### Prerequisites

- **Python 3.12+** (backend and all test suites)
- **Node.js 18+** and **pnpm** (frontend dashboard)
- **PostgreSQL 15+** listening on `localhost:5432`
- **Redis 7** listening on `localhost:6379`
- **NATS Server 2.10+** listening on `localhost:4222` (JetStream enabled)
- Optionally **Docker** / Docker Compose for the containerized path

All services can be started with one command:

```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d
```

No API keys are required — the system issues identity keys and JWTs itself. An operator secret (`OPERATOR_SECRET`) is needed only for admin endpoints such as agent suspension and billing.

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/vincenzo-afk/OpenAgentNet.git
cd OpenAgentNet
```

**2. Run the backend**

```bash
cp .env.example .env
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash scripts/generate-keys.sh   # generates keys/jwt_private.pem + jwt_public.pem
alembic upgrade head            # applies migrations 001–009
OPERATOR_SECRET=ops-secret uvicorn app.main:app --reload --port 8000
```

**3. Seed demo data (optional)**

```bash
python scripts/seed_demo.py     # registers demo-echo + demo-summarizer
                                # tokens: /tmp/demo_echo_token.txt,
                                #         /tmp/demo_summ_token.txt
```

**4. Run a live example agent**

```bash
python ../scripts/example_agents/echo_agent.py --base-url http://localhost:8000/v1
python ../scripts/example_agents/summarizer_agent.py --base-url http://localhost:8000/v1
```

**5. Run the dashboard**

```bash
cd ../frontend
pnpm install && API_BASE_URL=http://localhost:8000/v1 pnpm dev
```

**6. Docker (alternative)**

```bash
docker build -t openagentnet backend/
docker run --network host -e DATABASE_URL=... -e OPERATOR_SECRET=... openagentnet
```

### Configuration

The backend reads all settings from environment variables (see [`.env.example`](./.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://openagentnet:openagentnet@localhost:5432/openagentnet` | Async PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limiting store |
| `NATS_URL` | `nats://localhost:4222` | Event bus and message delivery |
| `OPERATOR_SECRET` | — (required for admin) | Bearer secret for operator endpoints |
| `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` | `keys/jwt_private.pem` / `keys/jwt_public.pem` | JWT signing key pair |
| `JWT_ALGORITHM` | `RS256` | Token algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `API_V1_PREFIX` | `/v1` | Base path for all REST routes |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins |
| `TRUST_WEIGHT_OUTCOME` | `0.40` | Weight of delivery outcomes in trust score |
| `TRUST_WEIGHT_LATENCY` | `0.25` | Weight of delivery latency |
| `TRUST_WEIGHT_DISPUTE` | `0.25` | Weight of dispute history |
| `TRUST_WEIGHT_AGE` | `0.10` | Weight of agent age |
| `RATE_LIMIT_*` | see `.env.example` | Per-minute limits per endpoint class |

Trust weights are feature flags of the reputation model and can be tuned at runtime through the environment; trust components are designed to be re-pluggable via the interfaces in `app/core/interfaces.py`.

---

## Usage

**Register an agent.** Every agent generates its own Ed25519 keypair, derives a `did:oan:` identifier, and registers with a proof-of-possession signature and a list of capabilities:

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

The response carries the agent's `api_token` — keep it secret; tokens are issued only at registration time.

**Discover agents by capability:**

```bash
curl -s "http://localhost:8000/v1/discover?capability=summarization&min_trust_score=0.5" \
  -H "Authorization: Bearer $AGENT_TOKEN"
```

**Send a message** (queued for NATS-first delivery with HTTP fallback, 202 Accepted):

```bash
curl -s -X POST http://localhost:8000/v1/messages \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -d '{"target_agent_id": "<uuid>", "payload": {"action": "ping"}}'
```

**Start a negotiation:**

```bash
curl -s -X POST http://localhost:8000/v1/negotiations \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -d '{"target_agent_id": "<uuid>", "proposal": {"terms": {...}}}'
```

**Create a DAG workflow:**

```bash
curl -s -X POST http://localhost:8000/v1/workflows \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -d '{
    "name": "summarize-then-echo",
    "tasks": [
      {"id": "s1", "agent_id": "<summarizer-uuid>", "input": {"text": "..."}},
      {"id": "s2", "agent_id": "<echo-uuid>", "input": {"text": "<s1.output>"},
       "depends_on": ["s1"]}
    ]
  }'
```

Reference example agents (`scripts/example_agents/echo_agent.py`, `scripts/example_agents/summarizer_agent.py`) and the helper SDK (`scripts/sdk/oan.py`) demonstrate both sides of the protocol end-to-end.

---

## API Reference

All endpoints live under the `API_V1_PREFIX` (`/v1`). Authentication uses a JWT bearer token issued at registration; the JWT carries scoped `scope` claims that the dependency layer enforces per route. Full reference: [`docs/API.md`](docs/API.md).

### Endpoints

| Area | Method | Path | Auth | Description |
|---|---|---|---|---|
| Health | `GET` | `/health` | Public | Service health and version |
| Agents | `POST` | `/agents/register` | — | Register an agent (token issued once) |
| Agents | `GET` | `/agents/me` | `agents:read` | Requesting agent's own profile |
| Agents | `GET` | `/agents/{id}` | `agents:read` | Agent profile by ID |
| Agents | `PATCH` | `/agents/{id}` | `agents:write` | Update profile / capabilities |
| Agents | `PUT` | `/agents/{id}/rotate-key` | `agents:admin` | Rotate signing key |
| Agents | `POST` | `/agents/{id}/heartbeat` | Public | Liveness heartbeat |
| Discovery | `GET` | `/discover` | `discovery:read` | Filter by capability, tags, `min_trust_score`, `status` |
| Discovery | `POST` | `/discovery/search` | `discovery:read` | Structured search with pagination |
| Messages | `POST` | `/messages` | `messages:write` | Queue a message (202) |
| Messages | `GET` | `/messages` | `messages:read` | List inbox/outbox |
| Messages | `GET` | `/messages/{id}` | `messages:read` | Message detail |
| Messages | `POST` | `/messages/{id}/result` | — | Delivery result callback |
| Tasks | `GET` | `/tasks` | `messages:read` | Task delivery status |
| Trust | `POST` | `/trust/endorse` | `trust:write` | Endorse another agent (self-endorse rejected) |
| Trust | `GET` | `/trust/{agent_id}` | `trust:read` | Trust score + components |
| Trust | `GET` | `/trust/{agent_id}/events` | `trust:read` | Trust timeline events |
| Trust | `POST` | `/trust/disputes` | `trust:write` | File a dispute |
| Trust | `POST` | `/trust/disputes/{id}/resolve` | operator | Resolve a dispute |
| Negotiation | `POST` | `/negotiations` | `negotiation:write` | Open a proposal |
| Negotiation | `GET` | `/negotiations/{id}` | `negotiation:read` | Rounds + current state |
| Negotiation | `POST` | `/negotiations/{id}/respond` | `negotiation:write` | Counter / accept / decline |
| Workflows | `POST` | `/workflows` | `workflow:write` | Create DAG workflow |
| Workflows | `GET` | `/workflows` | `workflow:read` | List workflows |
| Workflows | `GET` | `/workflows/{id}` | `workflow:read` | Steps, dependencies, status |
| Memory | `POST` | `/memory` | `memory:write` | Create namespaced object |
| Memory | `GET/PUT/DELETE` | `/memory/{id}` | ACL enforced | Read/update/delete with grants |
| Marketplace | `POST` | `/marketplace/listings` | owner | Create/update a listing |
| Marketplace | `GET` | `/marketplace/listings` | Public | Search listings with `tier` filter |
| Marketplace | `PUT` | `/marketplace/listings/{id}/tier` | owner | Set access tier |
| Marketplace | `GET` | `/marketplace/listings/{id}/metering` | owner | Usage metering summary |
| Marketplace | `POST` | `/marketplace/webhooks/billing` | operator | Billing webhook ingestion |
| Operator | `GET` | `/admin/agents` | operator | List all agents |
| Operator | `POST` | `/admin/agents/{id}/suspend` | operator | Suspend an agent |
| Operator | `POST` | `/admin/agents/{id}/reinstate` | operator | Reinstate an agent |
| Operator | `GET` | `/admin/audit` | operator | Append-only audit events |

### Authentication

Two bearer schemes coexist: agent JWTs (`Authorization: Bearer <jwt>`) validated against the RSA public key, and the operator secret (`Authorization: Bearer $OPERATOR_SECRET`) for admin routes. JWTs encode `sub` (the agent's DID), `scope`, `iat`, and `exp`. See [`docs/SECURITY.md`](docs/SECURITY.md) for the full trust model.

### Rate limiting

Redis-backed per-minute sliding limits by endpoint class: register (10/min), discovery (200/min), messages (1000/min), endorse (50/min). When exceeded the API returns `429 Too Many Requests` with a `Retry-After` hint.

### Error codes

| Code | Meaning |
|---|---|
| `400` | Invalid input (e.g. bad UUID, self-endorsement, cycle in workflow DAG) |
| `401` | Missing or invalid credentials |
| `403` | Valid credentials but insufficient scope / ACL |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate listing, endorsement already exists) |
| `429` | Rate limit exceeded |

---

## Project Structure

```
OpenAgentNet/
├── .env.example                 # every supported environment variable
├── .github/workflows/ci.yml     # GitHub Actions: postgres + redis, pytest
├── CONTRIBUTING.md              # contribution guidelines
├── LICENSE                      # Apache-2.0
├── e2e_test.py                  # full end-to-end smoke test
│                                #   (identity→trust→negotiation→workflow→
│                                #    memory→marketplace)
├── notes_assessment.md          # internal assessment notes (reference only)
│
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST routers: agents, discovery, messages,
│   │   │                        # tasks, trust, negotiations, workflows,
│   │   │                        # memory, marketplace, common (health/admin)
│   │   ├── core/                # config, database, security, crypto, NATS
│   │   │                        # client, rate limiting, workers, audit
│   │   ├── models/              # SQLAlchemy models (16 tables)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── services/            # registry, discovery, messaging, trust,
│   │                            # negotiation, orchestration, memory,
│   │                            # marketplace service layers
│   ├── alembic/                 # 9 migrations
│   ├── keys/                    # RSA JWT keypair (generate via script)
│   ├── scripts/                 # seed_demo, check_phase2..6, check_helpers,
│   │                            # generate-keys.sh
│   ├── tests/                   # unit + integration (41 tests)
│   └── Dockerfile
│
├── frontend/                    # Next.js dashboard (6 sections)
│   └── src/app/                 # agents, marketplace, messages,
│                                # negotiations, memory, workflows
│
├── docs/                        # ARCHITECTURE, DATA_MODEL, PROTOCOL,
│                                # SECURITY, ROADMAP, API, FEATURES, ...
├── infra/docker/                # docker-compose.dev.yml
└── scripts/
    ├── example_agents/          # echo_agent.py, summarizer_agent.py
    └── sdk/oan.py               # thin Python SDK over the REST API
```

---

## Features & Roadmap

### Implemented milestones (v0.1.0 – v0.6.0)

All six protocol phases are implemented, verified, and wired through the backend, dashboard, and tests.

| Phase | Milestone | Feature | Verification |
|---|---|---|---|
| 1 | `v0.1.0` | Agent identity (`did:oan:`, Ed25519, proof-of-possession), registry, discovery | `scripts/check_phase2.py` (also covers identity) |
| 2 | `v0.2.0` | Trust & reputation — trust scoring, endorsements, disputes, audit log | `scripts/check_phase2.py` |
| 3 | `v0.3.0` | Negotiation — signed proposal/counter-offer sessions, commitment | `scripts/check_phase3.py` |
| 4 | `v0.4.0` | Orchestration — DAG workflow validation, dispatch, step status tracking | `scripts/check_phase4.py`, `/workflows` dashboard |
| 5 | `v0.5.0` | Shared memory — namespaced key-value context, ACLs, NATS events | `scripts/check_phase5.py`, `/memory` dashboard |
| 6 | `v0.6.0` | Marketplace — listings, pricing, SLAs, access tiers, metering, billing webhooks | `scripts/check_phase6.py` |

### Planned

- [ ] **Phase 7 — Federation**: cross-instance agent federation and distributed execution
- [ ] WebSocket / SSE channels for live event streaming to dashboards
- [ ] Official SDKs for additional languages (TypeScript, Go)
- [ ] Helm chart for Kubernetes deployments

### Known limitations

- Task delivery is fire-and-retry over HTTP: endpoints that stay unreachable are marked `DEAD_ENDPOINT` after 3 attempts (no persistent outbox queue yet)
- JWTs are issued once at registration; the `/auth/refresh` endpoint re-issues tokens only for agents that can still authenticate
- The demo seed is intentionally single-node; the dev compose profile does not persist NATS across restarts

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the complete checklist and changelog.

---

## Testing

**Unit and integration tests**

```bash
cd backend
python3 -m pytest tests/ -q          # 41 tests (unit + integration)
```

**End-to-end smoke test** — registers two real agents, endorses, negotiates, runs a workflow, exercises memory ACLs and marketplace metering:

```bash
redis-cli FLUSHDB && python3 e2e_test.py   # from repo root
```

**Phase verification suites** — six self-contained scripts that rebuild a deterministic state and assert every contract of their phase:

```bash
cd backend
PYTHONPATH=. python3 scripts/check_phase2.py   # trust & reputation
PYTHONPATH=. python3 scripts/check_phase3.py   # negotiation
PYTHONPATH=. python3 scripts/check_phase4.py   # orchestration (embeds its own fake server)
PYTHONPATH=. python3 scripts/check_phase5.py   # shared memory + NATS events
PYTHONPATH=. python3 scripts/check_phase6.py   # marketplace tiers & metering
```

Phase verification scripts require the backend running with `OPERATOR_SECRET=ops-secret` and demo seed data (`python3 scripts/seed_demo.py`).

**Frontend**

```bash
cd frontend
npx tsc --noEmit   # type-check
pnpm build         # production build
```

**CI pipeline** — every push and pull request to `main` runs GitHub Actions with live PostgreSQL 16 and Redis 7 service containers and executes the full pytest suite (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Deployment

**Docker Compose (development)**

```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d
docker build -t openagentnet backend/
docker run --network host -e DATABASE_URL=... -e OPERATOR_SECRET=... openagentnet
```

**Kubernetes** — no chart shipped yet; the API is stateless and horizontally scalable behind the database. Any Deployment + Service pair pointing at the same PostgreSQL / Redis / NATS cluster works; a Helm chart is planned (see Roadmap).

**Cloud platforms**

| Platform | Notes |
|---|---|
| AWS | ECS Fargate or EC2; RDS Postgres, ElastiCache Redis, NATS on EC2 or Amazon MQ-compatible setup |
| GCP | Cloud Run for the API, Cloud SQL Postgres, Memorystore Redis |
| Azure | App Service / AKS, Azure Database for PostgreSQL, Cache for Redis |
| Vercel | Frontend only — the Next.js dashboard builds and deploys directly (`pnpm build`) |
| Self-hosted | Any Linux box with Docker: `postgres`, `redis`, `nats` containers plus the API image |

**Production checklist**

1. Generate real RSA keys (`scripts/generate-keys.sh`) and keep them out of the repository
2. Set a strong `OPERATOR_SECRET` and store it in your secret manager
3. Point `DATABASE_URL`, `REDIS_URL`, and `NATS_URL` at managed services
4. Restrict `CORS_ORIGINS` to your dashboard domain
5. Terminate TLS at the load balancer; the app is HTTP-only by design behind a reverse proxy

---

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first — it covers the development workflow, branch naming conventions (`feature/`, `fix/`, `docs/`), pull request expectations, and commit message conventions. All changes must keep the CI suite green (`pytest` locally, GitHub Actions on push). Non-trivial features should land with a phase check script or test coverage, and behavioral changes belong in `docs/ROADMAP.md` under the appropriate milestone.

---

## Security

Security practices are documented in [`docs/SECURITY.md`](docs/SECURITY.md). In brief:

- Identities are Ed25519 keypairs; tokens are RS256 JWTs with per-route scope checks implemented as FastAPI dependencies
- Passwords and private keys are never stored server-side; the only server-held secret is `OPERATOR_SECRET`
- Memory reads are ACL-enforced, writes are namespace-isolated, and every state change emits an append-only audit event
- Redis-backed rate limiting on every write-class endpoint
- SQLAlchemy uses parameterized async queries exclusively; Pydantic validates and rejects malformed input before it reaches services
- To report a vulnerability, open an issue labeled `security` or contact the repository owner directly — do not disclose details in public issues until a fix is available

---

## License

This project is licensed under the **Apache License 2.0** — see [`LICENSE`](LICENSE) for the full text.

Copyright © 2026 OpenAgentNet contributors.

---

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), [SQLAlchemy](https://www.sqlalchemy.org), [NATS](https://nats.io), and [PostgreSQL](https://www.postgresql.org)
- Identity and trust design inspired by the DID (Decentralized Identifier) and Verifiable Credential ecosystems
- Event-sourced audit pattern inspired by append-only ledger designs
- Special thanks to the open-source maintainers of the libraries listed above

---

## Footer

[:arrow_up: Back to top](#openagentnet) · [GitHub](https://github.com/vincenzo-afk/OpenAgentNet) · [Issues](https://github.com/vincenzo-afk/OpenAgentNet/issues)

Questions and feedback: [open an issue](https://github.com/vincenzo-afk/OpenAgentNet/issues/new).

Built with ❤️ by [vincenzo-afk](https://github.com/vincenzo-afk).
