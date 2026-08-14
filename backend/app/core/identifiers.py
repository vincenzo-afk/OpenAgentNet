"""Agent identity resolution utilities.

Per docs/DESIGN.md the agent identity MUST be deterministic: an agent can
compute its own identity offline from its public key, before registering.

To reconcile that with the PostgreSQL schema (agents.id is a UUID primary key
used across every foreign key), the deterministic identity is encoded as a
**UUIDv5 derived from the base58(sha256(public_key))[:24] digest**:

    digest  = base58(sha256(public_key_bytes))[:24]   # 24-char base58
    agent_id = UUIDv5(NAMESPACE_OAN, f"did:oan:{digest}")
    did     = f"did:oan:{agent_id}"

Consequences:
- Two registries independently derive the SAME id and DID for the same key
  (federated registries, per DESIGN.md rationale).
- The stored primary key is a valid PostgreSQL UUID, so all ORM models and
  foreign keys remain untouched.
- Every lookup helper in this module resolves an agent by either the UUID
  string OR the 24-char base58 digest OR the full DID, so API consumers never
  need to know about the derivation.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Union

import base58

NAMESPACE_OAN = uuid.UUID("8f3b2c1d-9e4a-4f6b-8d2e-1a7c5b9f3e0d")

Ident = Union[str, uuid.UUID]


def public_key_digest(public_key_bytes: bytes) -> str:
    """Deterministic 24-char base58 digest of a public key (DESIGN.md)."""
    digest = hashlib.sha256(public_key_bytes).digest()
    return base58.b58encode(digest).decode()[:24]


def derive_agent_id(digest: str) -> uuid.UUID:
    """Derive a deterministic UUIDv5 from the base58 digest."""
    return uuid.uuid5(NAMESPACE_OAN, f"did:oan:{digest}")


def derive_agent_id_from_bytes(public_key_bytes: bytes) -> uuid.UUID:
    return derive_agent_id(public_key_digest(public_key_bytes))


def build_did(agent_id: uuid.UUID | str) -> str:
    return f"did:oan:{agent_id}"


def parse_agent_id(value: str | None) -> uuid.UUID | None:
    """Resolve any accepted identifier form to a UUID.

    Accepted forms:
    - UUID string               -> parsed directly
    - 24-char base58 digest     -> deterministic UUIDv5
    - did:oan:<uuid|digest>     -> strip prefix then resolve
    """
    if not value:
        return None
    raw = value.strip()
    if raw.startswith("did:oan:"):
        raw = raw[8:]
    # Try direct UUID parse first (covers both forms)
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        pass
    # Try treating it as a 24-char base58 digest
    if 16 <= len(raw) <= 24:
        return derive_agent_id(raw)
    return None
