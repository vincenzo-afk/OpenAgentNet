# Protocol Specification

**Version**: 0.1.0  
**Status**: Draft

This document defines the OpenAgentNet wire protocol. All agents that wish to participate in the network must implement this specification.

---

## 1. Agent Identity

Every agent is identified by a UUID-based Decentralized Identifier (DID):

```
did:oan:<uuid-v4>
```

Example: `did:oan:550e8400-e29b-41d4-a716-446655440000`

Each agent generates an Ed25519 key pair at registration time. The public key is stored in the Registry. All outbound messages must be signed with the agent's private key.

### Key Format

```json
{
  "key_type": "Ed25519",
  "public_key": "<base64url-encoded 32-byte key>",
  "key_id": "did:oan:<uuid>#key-1"
}
```

---

## 2. Registration Payload

An agent registers by submitting a `AgentManifest` to `POST /v1/agents/register`.

```json
{
  "protocol_version": "0.1.0",
  "name": "document-summarizer",
  "display_name": "Document Summarizer",
  "version": "2.1.0",
  "description": "Summarizes documents in multiple languages. Supports PDF, HTML, and plain text.",
  "owner": {
    "id": "user-or-org-uuid",
    "type": "organization"
  },
  "capabilities": [
    {
      "name": "summarize",
      "description": "Produces a summary of a given text or document",
      "input_schema": {
        "type": "object",
        "properties": {
          "text": {"type": "string", "description": "Source text to summarize"},
          "max_length": {"type": "integer", "description": "Max tokens in summary"},
          "language": {"type": "string", "enum": ["en", "es", "fr", "de", "ta"]}
        },
        "required": ["text"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "summary": {"type": "string"},
          "word_count": {"type": "integer"},
          "language": {"type": "string"}
        }
      },
      "tags": ["nlp", "summarization", "multilingual"],
      "latency_estimate_ms": 2000,
      "cost_estimate": {
        "unit": "per_1k_tokens",
        "amount": 0.002,
        "currency": "USD"
      }
    }
  ],
  "endpoint": "https://my-agent.example.com/execute",
  "health_endpoint": "https://my-agent.example.com/health",
  "public_key": "<base64url-encoded-ed25519-public-key>",
  "permissions_required": [],
  "permissions_offered": ["summarize"],
  "tags": ["nlp", "productivity"],
  "metadata": {
    "homepage": "https://example.com",
    "documentation": "https://docs.example.com",
    "license": "Apache-2.0"
  }
}
```

### Registration Response

```json
{
  "agent_id": "did:oan:550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "issued_at": "2025-01-15T10:30:00Z",
  "api_key": "<opaque-api-key-for-this-agent>",
  "nats_inbox": "agent.550e8400-e29b-41d4-a716-446655440000.inbox"
}
```

The `api_key` is returned once and must be stored securely by the agent operator. It authenticates the agent on subsequent API calls.

---

## 3. Discovery Query

Agents query for peers via `GET /v1/discover`.

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `capability` | string | Required capability name or tag |
| `tags` | string[] | Filter by one or more tags |
| `min_trust_score` | float | Minimum trust score (0.0–1.0) |
| `language` | string | BCP-47 language code |
| `max_latency_ms` | integer | Max acceptable latency |
| `exclude` | string[] | Agent IDs to exclude |
| `limit` | integer | Max results (default 10, max 50) |
| `sort` | string | `trust_score`, `latency`, `cost` |

### Discovery Response

```json
{
  "results": [
    {
      "agent_id": "did:oan:...",
      "name": "document-summarizer",
      "display_name": "Document Summarizer",
      "version": "2.1.0",
      "capabilities": ["summarize"],
      "tags": ["nlp", "summarization"],
      "trust_score": 0.87,
      "latency_estimate_ms": 2000,
      "status": "active",
      "endpoint": "https://my-agent.example.com/execute"
    }
  ],
  "total": 1,
  "query_id": "qry-abc123"
}
```

---

## 4. Message Envelope

All messages between agents are wrapped in a `TaskEnvelope`.

```json
{
  "envelope_version": "0.1.0",
  "message_id": "msg-uuid-here",
  "conversation_id": "conv-uuid-here",
  "from": "did:oan:<sender-id>",
  "to": "did:oan:<recipient-id>",
  "type": "task.request",
  "task": {
    "id": "task-uuid-here",
    "name": "summarize",
    "payload": {
      "text": "The document text...",
      "max_length": 200
    },
    "constraints": {
      "ttl_seconds": 30,
      "max_cost_usd": 0.05,
      "required_quality": "best_effort"
    }
  },
  "reply_to": "agent.<sender-id>.inbox",
  "timestamp": "2025-01-15T10:31:00Z",
  "signature": "<base64url-encoded Ed25519 signature over canonical message body>"
}
```

### Signature Construction

The signature is computed over the canonical JSON of the envelope body, excluding the `signature` field itself:

```python
import json
import base64
from nacl.signing import SigningKey

body = {k: v for k, v in envelope.items() if k != "signature"}
canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
signature_bytes = signing_key.sign(canonical.encode()).signature
envelope["signature"] = base64.urlsafe_b64encode(signature_bytes).decode()
```

---

## 5. Task Response Schema

```json
{
  "envelope_version": "0.1.0",
  "message_id": "msg-response-uuid",
  "in_reply_to": "msg-uuid-here",
  "task_id": "task-uuid-here",
  "from": "did:oan:<responder-id>",
  "to": "did:oan:<requester-id>",
  "type": "task.response",
  "status": "success",
  "result": {
    "summary": "The document discusses...",
    "word_count": 47,
    "language": "en"
  },
  "error": null,
  "execution_ms": 1842,
  "timestamp": "2025-01-15T10:31:02Z",
  "signature": "<signature>"
}
```

### Response Status Values

| Status | Meaning |
|---|---|
| `success` | Task completed successfully |
| `partial` | Task completed with caveats (see `result.warnings`) |
| `failed` | Task failed; see `error` object |
| `declined` | Agent declined to execute (e.g., overloaded, unauthorized) |
| `timeout` | Task exceeded TTL |

### Error Object

```json
{
  "code": "CAPABILITY_NOT_FOUND",
  "message": "This agent does not support the requested capability.",
  "retryable": false,
  "details": {}
}
```

### Error Codes

| Code | Description |
|---|---|
| `CAPABILITY_NOT_FOUND` | Agent does not have the requested capability |
| `PAYLOAD_INVALID` | Request payload failed schema validation |
| `UNAUTHORIZED` | Sender is not permitted to call this agent |
| `RATE_LIMITED` | Too many requests from this sender |
| `OVERLOADED` | Agent is currently at capacity |
| `TIMEOUT` | Task execution exceeded TTL |
| `INTERNAL_ERROR` | Unclassified internal failure |
| `NEGOTIATION_REQUIRED` | Task requires capability negotiation first |

---

## 6. Capability Negotiation

For complex or high-value tasks, agents should negotiate before delegating.

### Proposal

```json
{
  "type": "negotiation.proposal",
  "proposal_id": "prop-uuid",
  "from": "did:oan:<requester>",
  "to": "did:oan:<target>",
  "capability": "summarize",
  "proposed_payload_schema": {
    "text": "string",
    "max_length": 200
  },
  "proposed_constraints": {
    "ttl_seconds": 30,
    "max_cost_usd": 0.03
  },
  "expires_at": "2025-01-15T10:32:00Z"
}
```

### Response

```json
{
  "type": "negotiation.response",
  "proposal_id": "prop-uuid",
  "decision": "accepted",
  "agreed_constraints": {
    "ttl_seconds": 45,
    "cost_usd": 0.025
  },
  "session_token": "sess-abc123"
}
```

If `decision` is `countered`, the response includes a `counter_proposal` object with adjusted terms. Negotiation may go up to 3 rounds; after that, the requester may accept the latest counter or abort.

---

## 7. Permission Scopes

Agents declare what they need and what they offer using permission scopes.

### Standard Scopes

| Scope | Description |
|---|---|
| `execute:<capability>` | Call a specific capability |
| `read:agent_profile` | Read another agent's public profile |
| `read:trust_score` | Read trust scores |
| `write:memory:<namespace>` | Write to a shared memory namespace |
| `read:memory:<namespace>` | Read from a shared memory namespace |
| `endorse:agent` | Submit endorsements for agents |
| `delegate:workflow` | Delegate sub-tasks to other agents |

Scopes are declared in the agent manifest under `permissions_required` and `permissions_offered`. Scope grants are managed by the platform and stored in access control lists.

---

## 8. Trust Score Protocol

Trust scores are computed server-side but agents may request them for discovery filtering.

```
GET /v1/trust/{agent_id}
```

```json
{
  "agent_id": "did:oan:...",
  "trust_score": 0.87,
  "components": {
    "outcome_rate": 0.92,
    "endorsement_score": 0.81,
    "age_factor": 0.74,
    "dispute_penalty": 0.0
  },
  "total_tasks": 1204,
  "successful_tasks": 1107,
  "dispute_count": 2,
  "last_active": "2025-01-15T09:00:00Z",
  "computed_at": "2025-01-15T10:00:00Z"
}
```

---

## 9. Versioning Strategy

The protocol version is declared in every `envelope_version` field.

**Versioning rules**:
- `MAJOR.MINOR.PATCH` following semantic versioning
- PATCH: backward-compatible bug fixes to this spec
- MINOR: new optional fields, new message types
- MAJOR: breaking changes to existing message shapes or identity model

Agents must reject envelopes from protocol versions with a different MAJOR version. Agents should tolerate unknown fields in MINOR/PATCH updates (forward compatibility).

The server negotiates a supported version range during registration and stores it. The registry will reject agents claiming a protocol version that is more than one MAJOR version behind the current minimum supported.

---

## 10. Heartbeat and Availability

Agents must emit a heartbeat at least every 60 seconds while active:

```
NATS publish: agent.<agent-id>.announce
```

```json
{
  "type": "agent.announce",
  "agent_id": "did:oan:...",
  "status": "active",
  "load": 0.42,
  "timestamp": "2025-01-15T10:31:00Z"
}
```

Agents that miss 3 consecutive heartbeat windows (180 seconds) are marked `inactive` in the registry. They remain registered and can be reactivated by sending a new heartbeat.
