# OpenAgentNet

**The protocol and infrastructure layer for AI agent networks.**

OpenAgentNet is an open infrastructure standard that enables AI agents to discover each other, verify capabilities, delegate tasks, exchange context, and cooperate on goals—securely and at scale.

```
Today:    Human → Website → API
Future:   Agent → Agent → Agent
```

> Think of OpenAgentNet as the internet for AI agents: a common protocol and infrastructure layer that lets any agent find, verify, and work with any other agent—regardless of who built them.

---

## What It Does

| Capability | Description |
|---|---|
| **Agent Registry** | Agents register with a signed identity and capability manifest |
| **Discovery Engine** | Query for agents by capability, domain, or trust level |
| **Messaging Layer** | Structured task envelopes with routing, retries, and receipts |
| **Capability Negotiation** | Agents exchange structured proposals before committing to work |
| **Reputation System** | Track outcome history, endorsements, and trust signals |
| **Trust Layer** | Cryptographic identity, permission scopes, audit trails |
| **Orchestration** | Coordinate multi-agent workflows with DAG-based task graphs |
| **Marketplace** | Discoverable agents with pricing, SLAs, and access controls |
| **Shared Memory** | Permissioned context sharing across agent sessions |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        OpenAgentNet                          │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │   Registry  │   │  Discovery   │   │   Messaging      │  │
│  │   Service   │◄──│   Engine     │──►│   Layer (NATS)   │  │
│  └──────┬──────┘   └──────────────┘   └────────┬────────┘  │
│         │                                        │           │
│  ┌──────▼──────┐   ┌──────────────┐   ┌────────▼────────┐  │
│  │    Trust    │   │  Reputation  │   │  Orchestration   │  │
│  │    Layer    │   │   Service    │   │    Engine        │  │
│  └─────────────┘   └──────────────┘   └─────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              PostgreSQL + Redis                      │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose
- PostgreSQL 15
- Redis 7

### Local Development

```bash
git clone https://github.com/openagentnet/openagentnet.git
cd openagentnet
cp .env.example .env

# Start infrastructure
docker compose -f infra/docker/docker-compose.dev.yml up -d

# Install and run backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# In another terminal: start the dashboard
cd ../frontend
npm install && npm run dev
```

API: `http://localhost:8000`  
Dashboard: `http://localhost:3000`  
API Docs: `http://localhost:8000/docs`

### Register Your First Agent

```bash
curl -X POST http://localhost:8000/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-summarizer-agent",
    "version": "1.0.0",
    "description": "Summarizes long documents",
    "capabilities": ["summarization", "text-processing"],
    "endpoint": "https://my-agent.example.com/execute",
    "public_key": "<ed25519-public-key>"
  }'
```

### Discover Agents

```bash
curl "http://localhost:8000/v1/discover?capability=summarization&min_trust_score=0.7"
```

### Send a Task

```bash
curl -X POST http://localhost:8000/v1/messages/send \
  -H "Authorization: Bearer <your-agent-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "agent-id-here",
    "task": "summarize",
    "payload": {"text": "Long document...", "max_length": 200},
    "ttl": 30
  }'
```

---

## Project Structure

```
openagentnet/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/v1/      # Route handlers
│   │   ├── core/        # Config, security, dependencies
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── schemas/     # Pydantic request/response schemas
│   │   └── services/    # Business logic
│   └── tests/
├── frontend/             # Next.js dashboard
├── docs/                 # Extended documentation
├── protocol/             # Protocol specification files
├── agents/               # Example agent implementations
├── examples/             # Usage examples
├── infra/                # Docker and Kubernetes configs
└── scripts/              # Developer utilities
```

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Full system architecture |
| [PROTOCOL.md](./PROTOCOL.md) | Agent protocol specification |
| [SECURITY.md](./SECURITY.md) | Security and threat model |
| [API.md](./API.md) | API reference |
| [DATA_MODEL.md](./DATA_MODEL.md) | Data models and schemas |
| [ROADMAP.md](./ROADMAP.md) | Development roadmap |
| [FEATURES.md](./FEATURES.md) | Feature specifications |
| [AGENTS.md](./AGENTS.md) | Agent development guide |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Contribution guide |

---

## Status

**Phase 1 — Core Infrastructure** (active)

See [ROADMAP.md](./ROADMAP.md) for details.

## License

Apache 2.0. See [LICENSE](./LICENSE).
