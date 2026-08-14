"""End-to-end smoke test of the OpenAgentNet registration flow."""
from __future__ import annotations

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

BASE = "http://127.0.0.1:8000/v1"

try:
    demo_token = open("/tmp/demo_token.txt").read().strip()
except FileNotFoundError:
    demo_token = ""


def main() -> int:
    failures: list[str] = []

    def check(label: str, resp: httpx.Response, expect: int = 200, detail: str | None = None):
        ok = resp.status_code == expect
        print(f"{label}: {resp.status_code}" + ("" if ok else f" expected {expect}"))
        if not ok:
            failures.append(label)
            print(resp.text[:400])
        if detail:
            print(detail)
        return ok

    # 1. Generate an Ed25519 identity for a new agent
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_key_b64 = base64.b64encode(public_bytes).decode()

    capabilities = [
        {
            "name": "summarization",
            "description": "Summarize long text",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
            "tags": [],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        },
        {
            "name": "text-processing",
            "description": "General text processing",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
            "tags": [],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        },
    ]

    # The backend signs the Pydantic model_dump() canonical form, which includes
    # all defaulted fields (display_name=null, health_endpoint=null, etc.), in
    # exactly the same shape the client should compute for reproducibility.
    manifest = {
        "protocol_version": "0.1.0",
        "name": f"e2e-summarizer-{random.randbytes(3).hex()}",
        "display_name": None,
        "version": "1.0.0",
        "description": "E2E test summarizer agent",
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": "Test Operator"},
        "capabilities": capabilities,
        "endpoint": "https://agent.example.com/execute",
        "health_endpoint": None,
        "public_key": public_key_b64,
        "permissions_required": [],
        "permissions_offered": [],
        "tags": ["llm", "text"],
        "metadata": {},
    }

    payload_bytes = encode_canonical_json(manifest)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = private_key.sign(payload_bytes + timestamp.encode())
    proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}

    with httpx.Client(base_url=BASE) as c:
        # 2. Register
        resp = c.post("/agents/register", json={"identity": manifest, "proof": proof})
        check("register", resp, 201)
        if resp.status_code != 201:
            return 1
        reg = resp.json()
        agent_id = reg["agent_id"]
        token = reg["api_token"]
        did = reg["did"]
        print(json.dumps(reg, indent=2, default=str)[:600])

        auth = {"Authorization": f"Bearer {token}"}

        # 3. Get agent profile
        resp = c.get(f"/agents/{agent_id}", headers=auth)
        check("get agent", resp)

        # 4. Discovery search (GET /v1/discover)
        resp = c.get("/discover?capability=summarization", headers=auth)
        check("discover", resp)

        # 4b. POST discovery search
        resp = c.post(
            "/discovery/search",
            headers=auth,
            json={"capabilities": ["summarization"], "limit": 10, "offset": 0},
        )
        check("discovery/search", resp)

        # 5. Heartbeat
        resp = c.post(f"/agents/{agent_id}/heartbeat", headers=auth)
        check("heartbeat", resp)

        # 6. Send a task message (POST /v1/messages)
        resp = c.post(
            "/messages",
            headers=auth,
            json={
                "to": agent_id,
                "type": "task.request",
                "task": {"name": "summarize", "payload": {"text": "Hello world " * 20, "nonce": random.randbytes(4).hex()}},
                "ttl_seconds": 60,
            },
        )
        check("send message", resp, 202)
        msg_id = resp.json().get("message_id")

        # 6b. List messages
        resp = c.get("/messages", headers=auth)
        check("list messages", resp)

        # 8. List tasks (create one via /v1/tasks)
        resp = c.post(
            "/tasks",
            headers=auth,
            json={
                "executor_id": agent_id,
                "capability_slug": "summarization",
                "payload": {"text": "another test payload", "nonce": random.randbytes(4).hex()},
                "ttl_seconds": 60,
            },
        )
        check("create task", resp, 201)
        resp = c.get("/tasks", headers=auth)
        check("list tasks", resp)

        # 9. Marketplace listing
        resp = c.post(
            "/marketplace/listings",
            headers=auth,
            json={
                "title": "Summarizer Pro",
                "long_description": "Test marketplace listing",
                "pricing": {"currency": "USD", "unit_price": 0.01, "unit": "token"},
                "is_public": True,
            },
        )
        check("marketplace create", resp, 201)
        resp = c.get("/marketplace/listings")
        check("marketplace search (anon)", resp)

        # 10. Memory object
        resp = c.post(
            "/memory",
            headers=auth,
            json={
                "namespace": "test",
                "key": "session-context-1",
                "data": {"last_summary": "hello"},
            },
        )
        check("memory create", resp, 201)
        resp = c.get("/memory", headers=auth)
        check("memory list", resp)

        # 11. Negotiations (Phase 3 state machine)
        # Register a dedicated summarizer agent so both participants hold valid
        # tokens; e2e agent proposes, target counters, target accepts.
        summary_capabilities = [
            {
                "name": "summarization",
                "description": "Summarize long text",
                "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
                "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
                "tags": [],
                "latency_estimate_ms": None,
                "cost_estimate": None,
            }
        ]
        target_private_key = ed25519.Ed25519PrivateKey.generate()
        target_public_bytes = target_private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        summary_manifest = dict(manifest)
        summary_manifest["name"] = f"e2e-target-summarizer-{random.randbytes(3).hex()}"
        summary_manifest["public_key"] = base64.b64encode(target_public_bytes).decode()
        summary_manifest["capabilities"] = summary_capabilities
        payload_bytes = encode_canonical_json(summary_manifest)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signature = target_private_key.sign(payload_bytes + timestamp.encode())
        proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}
        resp = c.post("/agents/register", json={"identity": summary_manifest, "proof": proof})
        check("register target", resp, 201)
        target_summarizer = resp.json().get("agent_id") if resp.status_code == 201 else None
        target_token = resp.json().get("api_token") if resp.status_code == 201 else None
        target_auth = {"Authorization": f"Bearer {target_token}"} if target_token else {}
        resp = c.post(
            "/negotiations",
            headers=auth,
            json={
                "target_id": target_summarizer or agent_id,
                "capability": "summarization",
                "proposed_payload_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
                "ttl_seconds": 300,
            },
        )
        print("negotiation create:", resp.status_code, resp.text[:200])
        neg_id = resp.json().get("negotiation_id") if resp.status_code == 201 else None
        if neg_id and target_summarizer:
            # Target counters with an alternative price
            resp = c.post(
                f"/negotiations/{neg_id}/respond",
                headers=target_auth,
                json={
                    "decision": "countered",
                    "counter_proposal": {"unit_price": 0.02},
                },
            )
            print("negotiation counter:", resp.status_code, resp.json().get("status") if resp.status_code == 200 else resp.text[:100])
            # Requester cannot decline its own counter-party negotiation (only participants can, but requester declining own deal is still a participant)
            resp = c.post(
                f"/negotiations/{neg_id}/respond",
                headers=auth,
                json={"decision": "declined"},
            )
            print("negotiation decline (wrong side, expect 400):", resp.status_code)
            resp = c.post(
                f"/negotiations/{neg_id}/respond",
                headers=target_auth,
                json={"decision": "accepted"},
            )
            print("negotiation accept:", resp.status_code, resp.json().get("status") if resp.status_code == 200 else resp.text[:100])
            resp = c.get(f"/negotiations/{neg_id}", headers=auth)
            print("negotiation get:", resp.status_code, "rounds:", len(resp.json().get("rounds", [])) if resp.status_code == 200 else "-")
            resp = c.get("/negotiations?limit=10", headers=auth)
            print("negotiation list:", resp.status_code, "total:", resp.json().get("total") if resp.status_code == 200 else "-")
        elif neg_id:
            resp = c.get(f"/negotiations/{neg_id}", headers=auth)
            print("negotiation get:", resp.status_code)

        # 12. Workflow creation
        resp = c.post(
            "/workflows",
            headers=auth,
            json={
                "name": "e2e-pipeline",
                "definition": {
                    "tasks": [
                        {
                            "id": "step-1",
                            "agent_capability": "summarization",
                            "payload": {"text": "workflow step"},
                            "depends_on": [],
                        }
                    ]
                },
                "context": {},
            },
        )
        print("workflow create:", resp.status_code, resp.text[:300])
        workflow_id = resp.json()["workflow_id"] if resp.status_code == 201 else None
        if workflow_id:
            resp = c.get(f"/workflows/{workflow_id}", headers=auth)
            print("workflow get:", resp.status_code)
            resp = c.get("/workflows", headers=auth)
            print("workflow list:", resp.status_code)

        # 13. Health
        resp = c.get("/health")
        check("health", resp, detail=str(resp.json()))

        # 14. Update agent
        resp = c.patch(
            f"/agents/{agent_id}",
            headers=auth,
            json={"display_name": "E2E Summarizer", "tags": ["llm", "text", "e2e"]},
        )
        check("update agent", resp)

        # 15. Endorsement + dispute round-trip
        resp = c.get(f"/trust/{agent_id}")
        check("trust score", resp, detail=str(resp.json()))
        resp = c.get(f"/trust/{agent_id}/events")
        check("trust events", resp)
        resp = c.post(
            "/trust/endorse",
            headers=auth,
            json={"to_agent_id": agent_id, "capability": "summarization", "comment": "E2E trust"},
        )
        print("endorse:", resp.status_code, resp.text[:200])
        # 16. Key rotation (standard base64 per backend base64_to_public_key)
        new_key = ed25519.Ed25519PrivateKey.generate()
        new_pub = new_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        resp = c.put(
            f"/agents/{agent_id}/rotate-key",
            headers=auth,
            json={"public_key": base64.b64encode(new_pub).decode()},
        )
        if resp.status_code != 200:
            print("rotate key:", resp.status_code, resp.text[:300])
            failures.append("rotate key")
        else:
            print("rotate key:", resp.status_code)

    print("\n=== RESULT ===")
    if failures:
        print(f"FAILED: {failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
