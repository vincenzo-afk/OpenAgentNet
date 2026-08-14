#!/usr/bin/env python3
"""Seed the OpenAgentNet database with demo agents and traffic.

Creates two example agents (echo + summarizer) end-to-end through the public
registration API, then generates a small amount of demo traffic (messages,
tasks, marketplace listings, memory objects, trust endorsements).

Requires the backend services to be running. Example::

    uvicorn app.main:app          # terminal 1
    nats-server --jetstream       # terminal 2 (see docs/SETUP.md)
    python3 seed_demo.py          # terminal 3
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import sys
import uuid
from datetime import datetime, timezone

import httpx
from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

BASE = "http://localhost:8000/v1"


def register(client: httpx.Client, name: str, capabilities: list[dict],
             description: str, endpoint: str) -> dict:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manifest = {
        "protocol_version": "0.1.0",
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "version": "1.0.0",
        "description": description,
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": "openagentnet-demo"},
        "capabilities": capabilities,
        "endpoint": endpoint,
        "health_endpoint": None,
        "public_key": base64.b64encode(public_bytes).decode(),
        "permissions_required": [],
        "permissions_offered": [],
        "tags": ["demo"],
        "metadata": {},
    }
    payload = encode_canonical_json(manifest)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = private_key.sign(payload + timestamp.encode())
    proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}

    resp = client.post("/agents/register", json={"identity": manifest, "proof": proof}, timeout=30)
    resp.raise_for_status()
    return {**resp.json(), "_private_key": private_key}


def echo_capabilities() -> list[dict]:
    return [
        {
            "name": "echo",
            "description": "Returns received text unchanged",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "tags": ["utility"],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        }
    ]


def summarizer_capabilities() -> list[dict]:
    return [
        {
            "name": "summarization",
            "description": "Summarizes long text",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
            "tags": ["llm", "text"],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument("--base-url", default=BASE)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(base_url=base_url, timeout=30) as client:
        echo = register(client, "demo-echo", echo_capabilities(),
                        "Demo echo agent seeded by scripts/seed_demo.py",
                        "http://localhost:8000/agent/execute/echo")
        summ = register(client, "demo-summarizer", summarizer_capabilities(),
                        "Demo summarizer agent seeded by scripts/seed_demo.py",
                        "http://localhost:8000/agent/execute/summarizer")

        for agent in (echo, summ):
            client.post(f"/agents/{agent['agent_id']}/heartbeat",
                        headers={"Authorization": f"Bearer {agent['api_token']}"})

        # Cross traffic: echo asks summarizer to summarize something.
        resp = client.post(
            "/messages",
            headers={"Authorization": f"Bearer {echo['api_token']}"},
            json={
                "to": summ["did"],
                "type": "task.request",
                "task": {
                    "name": "summarize",
                    "payload": {
                        "text": "OpenAgentNet is an open protocol for AI agent networking. "
                                "It defines identity, discovery, messaging, trust, and "
                                "marketplace primitives so heterogeneous agents can cooperate.",
                    },
                },
                "ttl_seconds": 300,
            },
        )
        print("sent message:", resp.status_code, resp.text[:200])

        # Marketplace listings + endorsement cross-trust.
        client.post(
            "/marketplace/listings",
            headers={"Authorization": f"Bearer {summ['api_token']}"},
            json={
                "title": "Summarization as a Service",
                "long_description": "Trivial extractive summarizer for demo purposes.",
                "pricing": {"currency": "USD", "unit_price": 0.01, "unit": "token"},
                "is_public": True,
            },
        )
        resp = client.post(
            "/trust/endorse",
            headers={"Authorization": f"Bearer {echo['api_token']}"},
            json={
                "to_agent_id": summ["agent_id"],
                "capability": "summarization",
                "comment": "Seeded demo endorsement",
            },
        )
        print("endorsement:", resp.status_code, resp.text[:120])

        # Discovery demo.
        resp = client.get("/discover?capability=summarization")
        agents = resp.json().get("agents", resp.json().get("items", []))
        print(f"discovery: {len(agents)} agent(s) match 'summarization'")

        with open("/tmp/demo_token.txt", "w") as f:
            f.write(summ["api_token"])
        print("Seed complete. Agent IDs:")
        print("  echo:      ", echo["agent_id"], echo["did"])
        print("  summarizer:", summ["agent_id"], summ["did"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
