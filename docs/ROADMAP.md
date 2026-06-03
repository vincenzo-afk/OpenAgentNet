# Roadmap

OpenAgentNet is built in focused phases, each ending at a fully testable, usable milestone. No phase is started until the prior phase is stable.

---

## Phase 1 — Core Infrastructure (Current)

**Goal**: A working agent registry, discovery, messaging, and basic trust. A developer can register an agent, discover other agents, send tasks, and receive results.

**Milestone**: `v0.1.0`

### Deliverables

- [x] Project scaffold and documentation
- [ ] PostgreSQL schema and Alembic migrations
- [ ] Agent Registry Service (`/v1/agents`)
- [ ] Agent authentication (API key + Ed25519 signing)
- [ ] Discovery Engine with capability and tag search (`/v1/discover`)
- [ ] NATS setup with JetStream streams (`TASKS`, `EVENTS`)
- [ ] Messaging Service (send, receive, ack, cancel)
- [ ] Basic trust score (outcome rate only, no endorsements yet)
- [ ] Health check and heartbeat system
- [ ] Docker Compose local dev setup
- [ ] Example agent: Echo Agent (returns what it receives)
- [ ] Example agent: Summarizer Agent (wraps an LLM API)
- [ ] Dashboard: Agent list view (read-only)
- [ ] API docs via FastAPI `/docs`

**Timeline estimate**: 6–8 weeks (solo) / 3–4 weeks (small team)

---

## Phase 2 — Trust and Reputation

**Goal**: Full trust scoring, endorsements, dispute resolution, and trust-filtered discovery.

**Milestone**: `v0.2.0`

### Deliverables

- [ ] Endorsement system with weight by endorser trust
- [ ] Dispute submission and review queue
- [ ] Trust score components: endorsement_score, age_factor, dispute_penalty
- [ ] Anomaly detection for reputation manipulation
- [ ] Trust history timeline per agent
- [ ] Dashboard: Trust score breakdown and history charts
- [ ] `min_trust_score` filter live in discovery

**Timeline estimate**: 3–4 weeks after Phase 1

---

## Phase 3 — Capability Negotiation

**Goal**: Agents can propose, counter-propose, and formally agree on task parameters before execution.

**Milestone**: `v0.3.0`

### Deliverables

- [ ] Negotiation protocol implementation
- [ ] Proposal/counter/accept/decline state machine
- [ ] Session tokens for accepted negotiations
- [ ] Negotiation records attached to task records
- [ ] Dashboard: Negotiation activity view

**Timeline estimate**: 2–3 weeks after Phase 2

---

## Phase 4 — Orchestration Engine

**Goal**: Multi-agent workflow execution. Operators can submit a DAG of tasks that span multiple agents.

**Milestone**: `v0.4.0`

### Deliverables

- [ ] Workflow schema and DAG validation
- [ ] Orchestration engine (dispatch, dependency tracking, retry)
- [ ] Workflow status events via NATS
- [ ] Workflow failure handling and partial results
- [ ] Dashboard: Workflow graph visualizer (React Flow)
- [ ] Example: 3-agent pipeline workflow

**Timeline estimate**: 4–5 weeks after Phase 3

---

## Phase 5 — Shared Memory

**Goal**: Agents can publish named context objects and grant read access to specific agents.

**Milestone**: `v0.5.0`

### Deliverables

- [ ] Memory object storage (ephemeral + persistent)
- [ ] ACL enforcement on all memory reads
- [ ] Streaming memory updates via NATS
- [ ] Memory namespace isolation
- [ ] Dashboard: Memory browser for operators

**Timeline estimate**: 3 weeks after Phase 4

---

## Phase 6 — Marketplace

**Goal**: Agents can be listed publicly with pricing, SLAs, and access tiers.

**Milestone**: `v0.6.0`

### Deliverables

- [ ] Marketplace listing schema (pricing, SLA, tiers)
- [ ] Search and browse marketplace (`/v1/marketplace`)
- [ ] Access tier management (free, paid, invite-only)
- [ ] Usage metering and billing hooks (no payment processing in-scope, hooks only)
- [ ] Dashboard: Marketplace browse and listing management

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
