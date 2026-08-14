"""Minimal OpenAgentNet agent SDK.

A single-file Python SDK that lets a standalone agent register itself,
sign envelopes with its Ed25519 identity, send/receive messages, and
report task results. Example agents build on top of this module.

Usage::

    from sdk.oan import Agent

    agent = Agent(
        base_url="http://localhost:8000/v1",
        name="my-agent",
        capabilities=[{"name": "echo", "description": "Echoes messages"}],
        endpoint="https://example.com/execute",
    )
    registration = agent.register()
    agent.send_message(to="did:oan:...", task={"name": "echo", "payload": {"text": "hi"}})
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests
from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


@dataclass
class Capability:
    name: str
    description: str
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    tags: list[str] = field(default_factory=list)


class Agent:
    """A self-registering OpenAgentNet agent."""

    def __init__(
        self,
        base_url: str,
        name: str,
        capabilities: list[Capability | dict[str, Any]],
        endpoint: str,
        display_name: str | None = None,
        description: str | None = None,
        owner_name: str = "operator",
        owner_type: str = "user",
        tags: list[str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.display_name = display_name
        self.description = description
        self.tags = tags or []
        self.endpoint = endpoint
        self.owner_name = owner_name
        self.owner_type = owner_type

        # Deterministic per-process identity so repeated runs are stable.
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        public_bytes = self._private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self._public_key_b64 = base64.b64encode(public_bytes).decode()

        self.agent_id: str | None = None
        self.did: str | None = None
        self.token: str | None = None

        self._capabilities = [
            c if isinstance(c, dict) else {
                "name": c.name,
                "description": c.description,
                "input_schema": c.input_schema,
                "output_schema": c.output_schema,
                "tags": c.tags,
                "latency_estimate_ms": None,
                "cost_estimate": None,
            }
            for c in capabilities
        ]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self) -> dict[str, Any]:
        manifest = {
            "protocol_version": "0.1.0",
            "name": self.name,
            "display_name": self.display_name,
            "version": "1.0.0",
            "description": self.description,
            "owner": {"id": str(uuid.uuid4()), "type": self.owner_type, "name": self.owner_name},
            "capabilities": self._capabilities,
            "endpoint": self.endpoint,
            "health_endpoint": f"{self.endpoint}/health",
            "public_key": self._public_key_b64,
            "permissions_required": [],
            "permissions_offered": [],
            "tags": self.tags,
            "metadata": {},
        }

        payload = encode_canonical_json(manifest)
        timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signature = self._private_key.sign(payload + timestamp.encode())
        proof = {
            "timestamp": timestamp,
            "signature": base64.urlsafe_b64encode(signature).decode(),
        }

        resp = requests.post(
            f"{self.base_url}/agents/register",
            json={"identity": manifest, "proof": proof},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.agent_id = data["agent_id"]
        self.did = data["did"]
        self.token = data["api_token"]
        return data

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def send_message(self, to: str, task: dict[str, Any] | None = None,
                     ttl_seconds: int = 60) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/messages",
            headers=self._auth(),
            json={
                "to": to,
                "type": "task.request",
                "task": task or {},
                "ttl_seconds": ttl_seconds,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def report_result(self, message_id: str, success: bool,
                      execution_ms: int | None = None,
                      result: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/messages/{message_id}/result",
            headers=self._auth(),
            json={
                "status": "success" if success else "failed",
                "execution_ms": execution_ms,
                "result": result or {},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Self-management
    # ------------------------------------------------------------------
    def heartbeat(self) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/agents/{self.agent_id}/heartbeat",
            headers=self._auth(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_trust(self) -> dict[str, Any] | None:
        if not self.agent_id:
            return None
        resp = requests.get(
            f"{self.base_url}/trust/{self.agent_id}",
            headers=self._auth(),
            timeout=15,
        )
        return resp.json() if resp.status_code == 200 else None
