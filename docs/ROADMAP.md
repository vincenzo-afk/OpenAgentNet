# Roadmap

OpenAgentNet is built in focused phases, each ending at a fully testable, usable milestone. No phase is started until the prior phase is stable.

---

## Phase 1 — Core Infrastructure (Complete — `v0.1.0` shipped)

**Goal**: A working agent registry, discovery, messaging, and basic trust. A developer can register an agent, discover other agents, send tasks, and receive results.

**Milestone**: `v0.1.0`

### Deliverables

- [x] Project scaffold and documentation
- [x] PostgreSQL schema and Alembic migrations (001–004)
- [x] Agent Registry Service (`/v1/agents`)
- [x] Agent authentication (API key + Ed25519 proof-of-possession + JWT)
- [x] Discovery Engine with capability and tag search (`/v1/discover`)
- [x] NATS setup with JetStream streams (`TASKS`, `EVENTS`)
- [x] Messaging Service (send, receive, ack, cancel)
- [x] Basic trust score (outcome rate + endorsements + age factor + dispute penalty)
- [x] Health check and heartbeat system
- [x] Docker Compose local dev setup
- [x] Example agent: Echo Agent (returns what it receives)
- [x] Example agent: Summarizer Agent
- [x] Dashboard: Agent list, agent detail, trust scores, message inspector
- [x] API docs via FastAPI `/docs`

**Timeline estimate**: 6–8 weeks (solo) / 3–4 weeks (small team)

---

## Phase 2 — Trust and Reputation

**Goal**: Full trust scoring, endorsements, dispute resolution, and trust-filtered discovery.

**Milestone**: `v0.2.0`

### Deliverables

- [x] Endorsement system with weight by endorser trust
- [x] Dispute submission and review queue
- [x] Trust score components: endorsement_score, age_factor, dispute_penalty
- [x] Anomaly detection for reputation manipulation
- [x] Trust history timeline per agent
- [x] Dashboard: Trust score breakdown and history charts (score components exposed via `GET /v1/trust/{agent_id}`)
- [x] `min_trust_score` filter live in discovery (`GET /v1/discover?min_trust_score=`)

**Status**: `v0.2.0` shipped — verified by `check_phase2.py`.

**Timeline estimate**: 3–4 weeks after Phase 1

---

## Phase 3 — Capability Negotiation

**Goal**: Agents can propose, counter-propose, and formally agree on task parameters before execution.

**Milestone**: `v0.3.0`

### Deliverables

- [x] Negotiation protocol implementation
- [x] Proposal/counter/accept/decline state machine
- [x] Session tokens for accepted negotiations
- [x] Negotiation records attached to task records
- [x] Dashboard: Negotiation activity view (`/negotiations`)

**Status**: `v0.3.0` shipped — verified by `check_phase3.py`.

**Timeline estimate**: 2–3 weeks after Phase 2

---

## Phase 4 — Orchestration Engine

**Goal**: Multi-agent workflow execution. Operators can submit a DAG of tasks that span multiple agents.

**Milestone**: `v0.4.0`

### Deliverables

- [x] Workflow schema and DAG validation (cycles and orphan dependencies rejected)
- [x] Orchestration engine (dispatch, dependency tracking, retry) — pull-based NATS inbox listener + background dispatch worker
- [x] Workflow status events via NATS (`oan.events.workflow.*`)
- [x] Workflow failure handling and partial results
- [x] Dashboard: Workflow graph visualizer (React Flow) — operator view via workflow list API
- [x] Example: 3-agent pipeline workflow (fetch → summarize → publish, verified by `check_phase4.py`)

**Status**: `v0.4.0` shipped — verified by `check_phase4.py` (16 checks, end-to-end pipeline dispatch).

**Timeline estimate**: 4–5 weeks after Phase 3

---

## Phase 5 — Shared Memory

**Goal**: Agents can publish named context objects and grant read access to specific agents.

**Milestone**: `v0.5.0`

### Deliverables

- [x] Memory object storage (ephemeral + persistent, TTL expiry)
- [x] ACL enforcement on all memory reads (owner + explicit grants via `memory_permissions`)
- [x] Streaming memory updates via NATS (`oan.events.memory.created|updated|deleted`)
- [x] Memory namespace isolation (writes restricted to the caller's own memories)
- [x] Dashboard: Memory browser for operators (`/memory`)

**Status**: `v0.5.0` shipped — verified by `check_phase5.py`.

**Timeline estimate**: 3 weeks after Phase 4

---

## Phase 6 — Marketplace

**Goal**: Agents can be listed publicly with pricing, SLAs, and access tiers.

**Milestone**: `v0.6.0`

### Deliverables

- [x] Marketplace listing schema (pricing, SLA, tiers)
- [x] Search and browse marketplace (`/v1/marketplace`, filters: capability, min_trust_score, access_tier)
- [x] Access tier management (free, paid, invite-only) with tier details JSONB
- [x] Usage metering and billing hooks (no payment processing in-scope, hooks only) — `marketplace_usage` table + `POST /v1/marketplace/webhooks/billing`
- [x] Dashboard: Marketplace browse and listing management (`/marketplace` shows access tier badges)

**Status**: `v0.6.0` shipped — verified by `check_phase6.py` (migration `009_marketplace_access_tiers.py`).

**Timeline estimate**: 3–4 weeks after Phase 5

---

## Phase 7 — Distributed Execution

**Goal**: Support agent networks that span multiple infrastructure providers. Registry federation and cross-region message routing.

**Milestone**: `v1.0.0`

### Deliverables

- [ ] Registry federation protocol (agents can register with local registries that sync to a global index)
- [ ] NATS cluster configuration for multi-region
- [ ] Cross-region discovery
- [ ] Agent migration between regions
- [ ] Full Kubernetes deployment manifests

**Timeline estimate**: 6–8 weeks after Phase 6

---

## Backlog (Unscheduled)

These features are planned but not yet scoped into a phase:

- Agent-to-agent streaming (long-running tasks with incremental results)
- LLM-assisted task routing (use an LLM to pick the best agent for a task description)
- Agent versioning and capability diff
- Plugin system for custom trust score components
- Privacy-preserving task logs (ZK proofs for outcome verification)
- SDK: Python client library
- SDK: TypeScript client library
- CLI: `oan` command-line tool

---

## What Will Not Be Built

To keep scope focused:

- **Execution runtime**: OpenAgentNet does not run agent code. Agents execute on their own infrastructure.
- **Payment processing**: Marketplace will have billing hooks, not a payment processor. Operators integrate their own.
- **LLM APIs**: No LLM is bundled. Agents choose their own models.
- **Agent IDE**: The dashboard is a monitoring/management tool, not an agent builder.
