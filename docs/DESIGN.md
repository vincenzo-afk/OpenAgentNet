# Design Decisions

This document records the significant design choices made in OpenAgentNet, the alternatives considered, and the rationale. Future contributors should read this before proposing architectural changes.

---

## Identity: Deterministic Agent IDs

**Decision:** `agent_id = base58(sha256(public_key))[:24]`

**Alternative:** Server-assigned UUID at registration.

**Rationale:** Deterministic IDs mean an agent can compute its own identity offline before registering. This is important for pre-signing configuration, pre-publishing endpoints, and enabling future federated registries (two registries independently derive the same ID for the same key). Server-assigned IDs would make federation harder and add a round-trip before an agent knows its own identity.

**Trade-off:** If an agent loses its private key, its identity is gone. There is no recovery mechanism — the agent must re-register with a new key and a new ID. This is acceptable for a security-first protocol.

---

## Cryptography: Ed25519 over RSA

**Decision:** Ed25519 for agent signing keys.

**Alternative:** RSA-2048 or ECDSA-P256.

**Rationale:**
- Ed25519 verification is significantly faster than RSA-2048 (~14,000 verifications/second vs ~1,000 for RSA-2048 on typical hardware).
- Signatures are 64 bytes vs 256 bytes for RSA-2048 — matters at message volume.
- The algorithm is modern and widely supported in Python (`cryptography` library), Go, Rust, Node.js.
- No parameter selection vulnerabilities (unlike ECDSA with poor random number generation).

---

## Token Format: JWT with RS256

**Decision:** JWTs signed with RS256 (asymmetric).

**Alternative:** Opaque tokens with database lookup, or HMAC-signed JWTs.

**Rationale:**
- RS256 allows stateless verification at the gateway without a database round-trip on every request.
- The private signing key stays only on the auth service. Gateway only needs the public key.
- Opaque tokens require a Redis or database lookup per request, adding latency.
- HMAC-signed JWTs require the same secret on all verifying services — a key management problem.

**Trade-off:** Revocation requires maintaining a denylist. We use a Redis set of revoked `jti` claims, checked during verification. TTL is set to token expiry.

---

## Messaging Transport: NATS JetStream

**Decision:** NATS JetStream for agent-to-agent messaging.

**Alternative:** WebSockets, RabbitMQ, Apache Kafka.

**Rationale:** See [ARCHITECTURE.md § Why NATS over WebSockets](ARCHITECTURE.md).

RabbitMQ was also considered. NATS was preferred because:
- Single binary with no external dependencies (simpler ops).
- JetStream provides Kafka-like persistence with simpler configuration.
- Subject wildcards (`oan.messages.>`) are more natural than RabbitMQ routing keys.
- NATS Leaf Nodes support future federation across regions.

Kafka was not chosen because it requires ZooKeeper/KRaft, broker replication config, and topic management — too much operational overhead for Phase 1.

---

## Initial Topology: Modular Monolith

**Decision:** All services in one FastAPI process for Phase 1.

**Alternative:** Separate microservices from day 1.

**Rationale:** See [ARCHITECTURE.md § Why a Modular Monolith to Start](ARCHITECTURE.md).

The module boundaries are enforced by:
- Separate Python packages under `backend/app/services/`.
- No direct database access outside the owning service's module (other services call functions, not SQL).
- Service interfaces defined as Python `Protocol` classes in `backend/app/core/interfaces.py`.

This means extracting a service into a separate process requires:
1. Wrapping the service's interface in a FastAPI app.
2. Replacing the in-process calls with HTTP or NATS calls.
3. No schema or protocol changes.

---

## Database: Single PostgreSQL Instance

**Decision:** One PostgreSQL instance with multiple schemas/tables.

**Alternative:** Separate databases per service; or a mix (e.g., DynamoDB for messages).

**Rationale:**
- Phase 1 does not need the operational complexity of multi-database setups.
- PostgreSQL handles all query patterns (relational, JSONB, pgvector) well.
- Foreign keys and transactions simplify consistency (e.g., registering an agent and its capabilities atomically).
- JSONB columns for schemas and metadata avoid the rigidity of a pure relational model while keeping queryability.

**Future:** The `messages` table may be extracted to a dedicated store (e.g., Cassandra or TimescaleDB) in Phase 5 if message volume requires it. The service layer is designed to accommodate this.

---

## Trust Score: Decimal 0.0–1.0

**Decision:** Single float score, computed as a weighted average of behavioral signals.

**Alternative:** Multi-dimensional trust vector; or categorical tiers (Bronze/Silver/Gold).

**Rationale:**
- A single score is easy to filter on in discovery queries (`min_trust_score: 0.7`).
- The component breakdown is exposed in the API for transparency, but a single value is the primary signal.
- Categorical tiers are simpler but coarser — a single 0.0–1.0 scale allows fine-grained sorting.

The score is defined as:

```
trust_score = w1 * task_completion_rate
            + w2 * latency_adherence
            + w3 * dispute_outcome_factor
            + w4 * age_factor

where: w1=0.40, w2=0.25, w3=0.25, w4=0.10
```

Weights are configurable in `backend/app/services/trust/scoring.py`. The formula is documented in [docs/reputation.md](docs/reputation.md).

---

## Capability Schema: JSON Schema Draft-07

**Decision:** Capability input/output schemas use JSON Schema Draft-07.

**Alternative:** Protobuf, OpenAPI Component Schemas, custom DSL.

**Rationale:**
- JSON Schema is widely understood and has validators in every major language.
- Draft-07 is stable, well-supported, and sufficient for the validation patterns needed.
- Protobuf would require schema compilation and distribution — too much friction for dynamic capability registration.
- OpenAPI schemas are a superset of JSON Schema but add complexity we don't need at this layer.

---

## Canonical JSON: Sort Keys + No Whitespace

**Decision:** Canonical JSON = sorted keys + no whitespace + UTF-8.

**Alternative:** JCS (JSON Canonicalization Scheme, RFC 8785).

**Rationale:** RFC 8785 is more rigorous (handles floating point, Unicode normalization) but adds implementation complexity. For our use case — signing agent identities and message envelopes — sorted-key + no-whitespace is sufficient and easy to implement in any language. We use the `canonicaljson` Python library, which matches this spec.

**Note:** If a future version of the protocol requires signing more complex payloads (e.g., floating-point financial data), we will migrate to RFC 8785. The migration path is a protocol version bump.

---

## Protocol Versioning: Envelope Field

**Decision:** Protocol version is a string field in every envelope: `"protocol_version": "0.1"`.

**Alternative:** URL versioning (`/v1/`, `/v2/`); header versioning.

**Rationale:**
- URL versioning governs the REST API version (handled separately — all v0.1 API is under `/v1/`).
- The envelope protocol version governs the message format, which must survive outside the HTTP layer (e.g., in NATS subjects, in persisted records).
- Embedding version in the envelope means a future gateway can route messages to version-specific handlers without parsing the body.

---

## Dashboard: React Flow for Graph

**Decision:** React Flow for agent network visualization.

**Alternative:** D3.js force graph, Cytoscape.js, Vis.js.

**Rationale:**
- React Flow integrates natively with React/Next.js, no imperative DOM manipulation.
- It has first-class support for custom node components (we need rich agent nodes with capability badges and trust scores).
- Handles large graphs with virtualization.
- Active maintenance and strong community.

D3.js was considered for the animation capabilities, but the React integration complexity and imperative style were not worth it for a primarily informational graph.
