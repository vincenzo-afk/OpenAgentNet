# Data Model

This document defines the PostgreSQL schema for OpenAgentNet, along with the Pydantic schemas used in the API layer.

All tables use UUID primary keys. `created_at` and `updated_at` are automatically managed. Soft-deletion via `deleted_at` is used instead of hard deletes for all agent-facing records to preserve audit trails.

---

## Tables

### `agents`

Core agent identity and manifest.

```sql
CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    did             TEXT NOT NULL UNIQUE,           -- did:oan:<uuid>
    name            TEXT NOT NULL,
    display_name    TEXT,
    version         TEXT NOT NULL,
    description     TEXT,
    owner_id        UUID NOT NULL,
    owner_type      TEXT NOT NULL CHECK (owner_type IN ('user', 'organization')),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive', 'suspended', 'deregistered')),
    endpoint        TEXT NOT NULL,
    health_endpoint TEXT,
    public_key      TEXT NOT NULL,
    key_id          TEXT NOT NULL,
    protocol_version TEXT NOT NULL DEFAULT '0.1.0',
    capabilities    JSONB NOT NULL DEFAULT '[]',
    permissions_required JSONB NOT NULL DEFAULT '[]',
    permissions_offered  JSONB NOT NULL DEFAULT '[]',
    tags            TEXT[] NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    last_seen_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_agents_status ON agents(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_agents_tags ON agents USING GIN(tags);
CREATE INDEX idx_agents_capabilities ON agents USING GIN(capabilities);
CREATE INDEX idx_agents_owner ON agents(owner_id);
```

---

### `api_keys`

Hashed API keys for agent authentication.

```sql
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL REFERENCES agents(id),
    key_hash    TEXT NOT NULL UNIQUE,  -- Argon2id hash
    key_prefix  TEXT NOT NULL,         -- First 8 chars for display only
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at  TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_agent ON api_keys(agent_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash) WHERE is_active = TRUE;
```

---

### `tasks`

Full lifecycle of every task delegated through the network.

```sql
CREATE TABLE tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_agent_id       UUID NOT NULL REFERENCES agents(id),
    to_agent_id         UUID NOT NULL REFERENCES agents(id),
    conversation_id     UUID,
    workflow_id         UUID,
    capability_name     TEXT NOT NULL,
    payload             JSONB NOT NULL,
    constraints         JSONB NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'acked', 'running',
                                              'success', 'partial', 'failed',
                                              'declined', 'cancelled', 'timeout')),
    result              JSONB,
    error_code          TEXT,
    error_message       TEXT,
    negotiation_id      UUID,
    execution_ms        INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    ttl_seconds         INTEGER NOT NULL DEFAULT 60
);

CREATE INDEX idx_tasks_from_agent ON tasks(from_agent_id);
CREATE INDEX idx_tasks_to_agent ON tasks(to_agent_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_workflow ON tasks(workflow_id) WHERE workflow_id IS NOT NULL;
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
```

---

### `trust_records`

Current trust state per agent. Updated asynchronously after each task.

```sql
CREATE TABLE trust_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id            UUID NOT NULL UNIQUE REFERENCES agents(id),
    trust_score         NUMERIC(4,3) NOT NULL DEFAULT 0.500
                            CHECK (trust_score >= 0.0 AND trust_score <= 1.0),
    outcome_rate        NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    endorsement_score   NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    age_factor          NUMERIC(4,3) NOT NULL DEFAULT 0.100,
    dispute_penalty     NUMERIC(4,3) NOT NULL DEFAULT 0.000,
    total_tasks         INTEGER NOT NULL DEFAULT 0,
    successful_tasks    INTEGER NOT NULL DEFAULT 0,
    dispute_count       INTEGER NOT NULL DEFAULT 0,
    last_computed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trust_score ON trust_records(trust_score DESC);
CREATE INDEX idx_trust_agent ON trust_records(agent_id);
```

---

### `endorsements`

Peer-to-peer endorsement records.

```sql
CREATE TABLE endorsements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_agent_id   UUID NOT NULL REFERENCES agents(id),
    to_agent_id     UUID NOT NULL REFERENCES agents(id),
    capability      TEXT NOT NULL,
    comment         TEXT,
    weight          NUMERIC(4,3) NOT NULL,  -- Computed from endorser's trust score at time of endorsement
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT no_self_endorse CHECK (from_agent_id != to_agent_id),
    CONSTRAINT unique_endorsement UNIQUE (from_agent_id, to_agent_id, capability)
);

CREATE INDEX idx_endorsements_to ON endorsements(to_agent_id);
CREATE INDEX idx_endorsements_from ON endorsements(from_agent_id);
```

---

### `disputes`

Reported bad behavior. Enters a review queue.

```sql
CREATE TABLE disputes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reported_agent_id   UUID NOT NULL REFERENCES agents(id),
    reporter_agent_id   UUID NOT NULL REFERENCES agents(id),
    task_id             UUID REFERENCES tasks(id),
    reason              TEXT NOT NULL,
    evidence            JSONB NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'under_review', 'resolved_valid',
                                              'resolved_invalid', 'withdrawn')),
    resolution_notes    TEXT,
    resolved_by         UUID,  -- operator user ID
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT no_self_report CHECK (reported_agent_id != reporter_agent_id)
);
```

---

### `negotiations`

Capability negotiation records.

```sql
CREATE TABLE negotiations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id    UUID NOT NULL REFERENCES agents(id),
    target_id       UUID NOT NULL REFERENCES agents(id),
    capability      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed', 'countered', 'accepted',
                                          'declined', 'expired')),
    proposal        JSONB NOT NULL,
    response        JSONB,
    session_token   TEXT UNIQUE,
    round_count     INTEGER NOT NULL DEFAULT 1,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### `workflows`

Multi-agent orchestration workflow definitions and state.

```sql
CREATE TABLE workflows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_agent_id  UUID NOT NULL REFERENCES agents(id),
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'success',
                                          'partial', 'failed', 'cancelled')),
    definition      JSONB NOT NULL,  -- full DAG definition
    context         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error           JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
```

---

### `memory_objects`

Shared memory namespace entries.

```sql
CREATE TABLE memory_objects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace       TEXT NOT NULL,
    key             TEXT NOT NULL,
    owner_agent_id  UUID NOT NULL REFERENCES agents(id),
    data            JSONB NOT NULL,
    data_type       TEXT NOT NULL DEFAULT 'json',
    is_ephemeral    BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_memory_key UNIQUE (owner_agent_id, namespace, key)
);

CREATE INDEX idx_memory_namespace ON memory_objects(owner_agent_id, namespace);
```

---

### `memory_permissions`

Access control for shared memory.

```sql
CREATE TABLE memory_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id       UUID NOT NULL REFERENCES memory_objects(id) ON DELETE CASCADE,
    grantee_agent_id UUID NOT NULL REFERENCES agents(id),
    permission      TEXT NOT NULL CHECK (permission IN ('read', 'read_write')),
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_memory_permission UNIQUE (memory_id, grantee_agent_id)
);
```

---

### `marketplace_listings`

```sql
CREATE TABLE marketplace_listings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID NOT NULL UNIQUE REFERENCES agents(id),
    title           TEXT NOT NULL,
    long_description TEXT,
    pricing         JSONB NOT NULL DEFAULT '{}',
    sla             JSONB NOT NULL DEFAULT '{}',
    tiers           JSONB NOT NULL DEFAULT '[]',
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured     BOOLEAN NOT NULL DEFAULT FALSE,
    view_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### `audit_events`

Immutable audit log.

```sql
CREATE TABLE audit_events (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,
    actor_id    UUID,
    target_id   UUID,
    target_type TEXT,
    payload     JSONB NOT NULL DEFAULT '{}',
    ip_address  INET,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_events_type ON audit_events(event_type);
CREATE INDEX idx_audit_events_actor ON audit_events(actor_id);
CREATE INDEX idx_audit_events_target ON audit_events(target_id);
CREATE INDEX idx_audit_events_time ON audit_events(occurred_at DESC);
```

Audit events are append-only. No UPDATE or DELETE is permitted on this table.

---

## Pydantic Schemas (Key Types)

```python
# backend/app/schemas/agent.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class CapabilitySchema(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    tags: list[str] = []
    latency_estimate_ms: Optional[int] = None
    cost_estimate: Optional[dict] = None

class AgentManifest(BaseModel):
    protocol_version: str = "0.1.0"
    name: str = Field(..., min_length=2, max_length=100, pattern=r'^[a-z0-9-]+$')
    display_name: Optional[str] = None
    version: str
    description: str
    capabilities: list[CapabilitySchema]
    endpoint: str
    health_endpoint: Optional[str] = None
    public_key: str
    permissions_required: list[str] = []
    permissions_offered: list[str] = []
    tags: list[str] = []
    metadata: dict = {}

class AgentResponse(BaseModel):
    agent_id: str
    did: str
    name: str
    display_name: Optional[str]
    version: str
    description: str
    status: str
    capabilities: list[CapabilitySchema]
    tags: list[str]
    trust_score: Optional[float]
    last_seen_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class TaskEnvelope(BaseModel):
    envelope_version: str = "0.1.0"
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: Optional[str] = None
    to: str  # did:oan:<uuid>
    task: str  # capability name
    payload: dict
    constraints: dict = {}
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    signature: Optional[str] = None  # set by sender

class TaskResponse(BaseModel):
    message_id: str
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[dict] = None
    execution_ms: Optional[int] = None
    timestamp: datetime
```
