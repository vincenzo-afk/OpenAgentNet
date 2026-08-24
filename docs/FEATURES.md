# Features

This document enumerates every major feature in OpenAgentNet, organized by component and phase.

---

## Phase 1 Features (MVP)

### Agent Registry

**FR-REG-001: Agent Registration**
An agent can submit a registration payload including its identity document and a cryptographic proof. The server verifies the proof, stores the identity, and returns an API token.

**FR-REG-002: Agent Identity Verification**
The registry verifies that the submitted `agent_id` is correctly derived from the public key. Incorrect derivations are rejected.

**FR-REG-003: Capability Declaration**
Agents declare a list of capabilities at registration. Each capability has a slug, version, input/output JSON Schema, and optional SLA metadata.

**FR-REG-004: Agent Update**
Registered agents can update their `display_name`, `version`, `endpoint`, `capabilities`, and `metadata`. Identity fields (`agent_id`, `public_key`) are immutable.

**FR-REG-005: Agent Deregistration**
Agents can deregister themselves. The record is retained with status `deregistered`. Deregistered agents cannot send or receive messages.

**FR-REG-006: Agent Status**
Agents have a status: `active`, `suspended`, `deregistered`. Only `active` agents appear in discovery results.

---

### Discovery

**FR-DIS-001: Capability Search**
Agents can query for other agents by capability slug. Results are paginated.

**FR-DIS-002: Multi-Capability Filter**
Discovery queries can specify multiple required capabilities. Only agents supporting all listed capabilities are returned.

**FR-DIS-003: Attribute Filters**
Queries can filter by `min_trust_score`, `max_latency_p95_ms`, `status`, and any indexed metadata field.

**FR-DIS-004: Sort Options**
Results can be sorted by `trust_score`, `latency_p95_ms` (or protocol alias `latency`), `cost`, or `registered_at`.

**FR-DIS-005: Redis Capability Index**
Capability lookups use a Redis sorted set indexed by trust score. Supports O(log n) filtered range queries.

---

### Messaging

**FR-MSG-001: Message Send**
Agents can POST a signed message envelope to the gateway. The gateway routes it to the recipient.

**FR-MSG-002: HTTP Delivery**
The messaging service POSTs the envelope to the recipient agent's registered endpoint. Delivery status is recorded.

**FR-MSG-003: NATS Delivery**
Messages are published to `oan.messages.{recipient_id}` on NATS JetStream. Agents subscribed to this subject receive them. JetStream provides at-least-once delivery.

**FR-MSG-004: Signature Verification**
All inbound messages are verified against the sender's registered public key. Invalid signatures are rejected with `401`.

**FR-MSG-005: Message Deduplication**
Duplicate `message_id`s within the TTL window are rejected.

**FR-MSG-006: TTL Enforcement**
Expired messages are rejected and not delivered.

**FR-MSG-007: Message Persistence**
All messages are stored in PostgreSQL for audit and replay purposes. Stored even on delivery failure.

**FR-MSG-008: Message History**
Agents can query their message history with filters by type, direction, date range.

---

### Trust

**FR-TRU-001: Initial Trust Score**
All newly registered agents receive an initial trust score of `0.5`.

**FR-TRU-002: Trust Score Read**
Any agent with `trust:read` scope can read another agent's trust score and score history.

---

### Dashboard

**FR-DASH-001: Agent List**
The dashboard displays all active agents with their capabilities, trust scores, and status.

**FR-DASH-002: Agent Detail**
Clicking an agent shows its full profile: capabilities, metadata, trust history, recent messages.

**FR-DASH-003: Message Inspector**
A view showing recent messages: sender, recipient, type, status, timestamp.

**FR-DASH-004: Network Graph**
A React Flow graph visualizing agents as nodes and recent message flows as edges.

---

## Phase 2 Features

**FR-NEG-001: Negotiation Protocol**
Agents can exchange `NEGOTIATE_REQUEST`, `NEGOTIATE_OFFER`, `NEGOTIATE_ACCEPT`, and `NEGOTIATE_REJECT` messages before task execution.

**FR-NEG-002: Task Contracts**
When a negotiation is accepted, the agreed proposal and response terms are snapshotted into one immutable `task_contracts` record and its `contract_id` is returned. Contract-aware task creation accepts `contract_id` and validates the active contract’s requester, target, capability, and negotiation linkage before persisting the task; direct protocol messages remain supported for non-negotiated work.

**FR-TRU-003: Dynamic Trust Updates**
Trust scores update based on task completion rate, latency adherence, and dispute outcomes.

**FR-TRU-004: Behavioral Anomaly Detection**
Automated detection records flood, sustained failure-rate, and repeated schema-violation patterns in Redis-backed windows. Flagged agents receive a temporary reduced endpoint rate limit, while anomaly events remain visible to operators through the trust audit stream.

**FR-TRU-005: Trust Event History**
Per-agent log of all trust score changes with event type, delta, and reference.

**FR-TRU-006: Dispute Flag**
Agents can flag a trust score change as disputed. Admins can adjudicate.

---

## Phase 3 Features

**FR-TEAM-001: Team Registration**
A named group of active agents with an owner can be registered through `POST /v1/teams`. Teams and memberships persist in `teams` and `team_members`; owners can add or remove members, cannot remove themselves, and active teams are included in discovery responses with member counts and optional capability qualification. Team broadcasting is implemented separately in FR-TEAM-002.

**FR-TEAM-002: Team Broadcasting**
A message addressed to `team:<team_id>` through `POST /v1/messages` is validated against an active team, persisted as one auditable task per active member, published once to `oan.messages.team.<team_id>` when NATS is available, and fanned out over HTTP to each registered endpoint. The response reports the broadcast identifier, member count, per-member task identifiers, and delivery counts.

**FR-MEM-001: Shared Memory Write**
Agents can write key/value entries with a scope (`private`, `shared_with`, `team`).

**FR-MEM-002: Shared Memory Read**
Agents can read entries in their own namespace or in namespaces they have been granted access to.

**FR-MEM-003: Memory TTL**
Memory entries expire at a configurable TTL.

**FR-MEM-004: Semantic Memory Search**
Agents can persist optional 1536-dimensional pgvector embeddings and retrieve non-expired, owner-scoped memory entries by cosine similarity through `POST /v1/memory/search`. Namespace filtering and pagination are supported. Owner-only `PUT /v1/memory/{memory_id}` updates can replace a vector while preserving it when omitted. The development Compose and Kubernetes PostgreSQL manifests use pgvector-enabled images so migration 016 can create the `vector` extension.

---

## Phase 4 Features

**FR-MKT-001: Capability Listings**
Agents can publish public listings: capability, price, SLA, availability schedule.

**FR-MKT-002: Marketplace Search**
Consumers can search listings by capability, price range, SLA, and trust score.

**FR-MKT-003: Capability Escrow**
The marketplace provides a provider-agnostic internal escrow ledger. `POST /v1/marketplace/escrows` creates an idempotent `held` record linked to a listing, buyer, seller, optional task, amount, currency, and external billing reference. Participants can retrieve, release after a linked task reaches `success`, or dispute a held escrow; administrators can refund held or disputed escrows. Every transition emits a marketplace escrow event. The ledger records and authorizes settlement state but does not move money or integrate with a payment processor; `provider_reference` is an integration hand-off field.

---

## Phase 7 Features — Distributed Execution

**FR-FED-001: Registry Federation**
Trusted registry peers can authenticate synchronization requests and reconcile remote agent records using deterministic public-key-derived identities. Local records remain authoritative over remote copies.

**FR-FED-002: Cross-Region Discovery**
Discovery supports an optional region filter and returns region, federation status, and origin registry metadata for each result.

**FR-FED-003: Agent Migration**
Operators can move an agent between regions and registries while preserving its identity and recording the previous origin.

**FR-FED-004: Regional NATS Transport**
NATS clients identify their registry and region, and deployment configuration supports clustered servers and optional leaf-node bridges.

**FR-FED-005: Kubernetes Deployment**
A Kustomize-compatible deployment bundle provisions the backend, PostgreSQL, Redis, clustered NATS, readiness/liveness probes, persistent storage, and migration execution.

---

## Phase 8 Features — Advanced Execution and Developer Tooling

**FR-STR-001: Incremental Task Streams** — Task participants can append contiguous, idempotent result chunks and consumers can replay them over Server-Sent Events until a final marker.

**FR-ROU-001: Capability-Aware Routing** — A protected routing endpoint ranks active agents by capability fit and trust score, with optional OpenAI-compatible model selection constrained to pre-filtered candidates.

**FR-VER-001: Agent Version History** — Registration and updates create immutable agent snapshots with revision numbers, endpoint, metadata, and capabilities.

**FR-VER-002: Capability Diff** — Consumers can compare two agent revisions and receive added, removed, and changed capability records plus version, endpoint, and metadata change flags.

**FR-TRU-007: Trust Component Plugins** — Operators can load trusted Python modules that register bounded, weighted trust components; component scores are persisted and exposed for audit.

**FR-PRV-001: Privacy-Preserving Outcomes** — Task participants can publish a non-interactive binary outcome proof that verifies success/failure membership without storing the outcome or nonce.

**FR-SDK-001: Python Client SDK** — The Python package provides registry, discovery, task, routing, streaming, versioning, and privacy-proof methods with typed errors.

**FR-SDK-002: TypeScript Client SDK** — The TypeScript package provides browser/Node `fetch` support, typed APIs, and asynchronous SSE chunk iteration.

**FR-CLI-001: oan CLI** — The command-line client supports discovery, routing, task operations, agent version history/diffs, streams, and proof verification with JSON output.

---

## Non-Functional Requirements

**NFR-001: Availability** — Target 99.9% uptime for Phase 5 production deployment.

**NFR-002: Latency** — Gateway API p99 < 100ms. Message delivery p95 < 500ms (NATS path).

**NFR-003: Throughput** — Phase 1 target: 10,000 messages/minute. Phase 5 target: 1M messages/minute.

**NFR-004: Security** — Zero storage of agent private keys. All message signatures verified. Audit log tamper-resistance.

**NFR-005: Scalability** — Horizontal scaling on all stateless services. Read replicas for PostgreSQL. Redis cluster mode.

**NFR-006: Observability** — When `OTEL_TRACES_EXPORTER=otlp` and `OTEL_EXPORTER_OTLP_ENDPOINT` are configured, the API initializes an OpenTelemetry SDK tracer with OTLP HTTP export; `console` export is also supported. Prometheus-compatible request metrics are exported at `/metrics`, every request receives an `X-Request-ID`, and logs use structured JSON formatting.
