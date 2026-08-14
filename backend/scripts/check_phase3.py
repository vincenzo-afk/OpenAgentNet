#!/usr/bin/env python3
"""Phase 3 verification: negotiation state machine, counter-proposals, list, expiry."""
from __future__ import annotations

import base64
import time
import uuid
from datetime import datetime, timezone

import httpx
from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

BASE = "http://localhost:8000/v1"


def register_agent(name: str, capabilities: list[dict]) -> tuple[str, str]:
    """Register an agent and return (agent_id, api_token). Also heartbeats it."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manifest = {
        "protocol_version": "0.1.0",
        "name": f"{name}-{uuid.uuid4().hex[:6]}",
        "display_name": None,
        "version": "1.0.0",
        "description": f"Phase 3 {name}",
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": "phase3-test"},
        "capabilities": capabilities,
        "endpoint": f"http://localhost:8000/agent/execute/{name}",
        "health_endpoint": None,
        "public_key": base64.b64encode(public_bytes).decode(),
        "permissions_required": [],
        "permissions_offered": [],
        "tags": [],
        "metadata": {},
    }
    payload_bytes = encode_canonical_json(manifest)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = private_key.sign(payload_bytes + timestamp.encode())
    proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}

    with httpx.Client(base_url=BASE, timeout=15) as client:
        resp = client.post("/agents/register", json={"identity": manifest, "proof": proof})
        resp.raise_for_status()
        reg = resp.json()
        client.post(f"/agents/{reg['agent_id']}/heartbeat",
                    headers={"Authorization": f"Bearer {reg['api_token']}"})
    return reg["agent_id"], reg["api_token"]


def summarize_capabilities() -> list[dict]:
    return [
        {
            "name": "summarization",
            "description": "Summarizes long text",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
            "tags": [],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        }
    ]


def processing_capabilities() -> list[dict]:
    return [
        {
            "name": "text-processing",
            "description": "General text processing",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
            "tags": [],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        }
    ]


def proposal_body(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "capability": "summarization",
        "proposed_payload_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
        "ttl_seconds": 300,
    }


def main() -> int:
    req_id, req_token = register_agent("phase3-requester", processing_capabilities())
    tgt_id, tgt_token = register_agent("phase3-summarizer", summarize_capabilities())
    req_auth = {"Authorization": f"Bearer {req_token}"}
    tgt_auth = {"Authorization": f"Bearer {tgt_token}"}
    fails = []

    with httpx.Client(base_url=BASE, timeout=20) as client:
        # 1. Create proposal (requester -> target)
        r = client.post("/negotiations", headers=req_auth, json=proposal_body(tgt_id))
        print("create:", r.status_code)
        if r.status_code != 201:
            print(r.text[:300])
            return 1
        neg_id = r.json()["negotiation_id"]

        # 2. Non-participant response rejected
        other_id, other_token = register_agent("phase3-outsider", processing_capabilities())
        r = client.post(
            f"/negotiations/{neg_id}/respond",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"decision": "accepted"},
        )
        print("outsider (expect 400):", r.status_code, r.json().get("detail", "")[:60])
        if r.status_code != 400:
            fails.append("outsider")

        # 3. Requester cannot accept own proposal immediately? (allowed: any participant)
        # Instead verify target counters successfully.
        r = client.post(f"/negotiations/{neg_id}/respond", headers=tgt_auth, json={
            "decision": "countered",
            "counter_proposal": {"unit_price": 0.02},
        })
        print("counter:", r.status_code, r.json().get("status"), "round:", r.json().get("round_number"))
        if r.status_code != 200 or r.json().get("status") != "countered":
            fails.append("counter")
        if r.json().get("round_number") != 2:
            fails.append("round number")

        # 4. Requester double-counters
        r = client.post(f"/negotiations/{neg_id}/respond", headers=req_auth, json={
            "decision": "countered",
            "counter_proposal": {"unit_price": 0.015},
        })
        print("double-counter:", r.status_code, r.json().get("status"), "round:", r.json().get("round_number"))
        if r.status_code != 200 or r.json().get("status") != "countered":
            fails.append("double-counter")

        # 5. Max rounds: round_count is 3; a 4th counter must be rejected
        r = client.post(f"/negotiations/{neg_id}/respond", headers=tgt_auth, json={
            "decision": "countered",
            "counter_proposal": {"unit_price": 0.025},
        })
        print("third counter (round 4, expect 400):", r.status_code, r.json().get("detail", "")[:60])
        if r.status_code != 400:
            fails.append("max rounds not enforced")

        # 6. Fresh negotiation: decline
        r = client.post("/negotiations", headers=req_auth, json=proposal_body(tgt_id))
        neg2 = r.json()["negotiation_id"]
        r = client.post(f"/negotiations/{neg2}/respond", headers=tgt_auth, json={"decision": "declined"})
        print("decline:", r.status_code, r.json().get("status"))
        if r.status_code != 200 or r.json().get("status") != "declined":
            fails.append("decline")

        # 7. Fresh negotiation: accept with agreed constraints
        r = client.post("/negotiations", headers=req_auth, json=proposal_body(tgt_id))
        neg3 = r.json()["negotiation_id"]
        r = client.post(f"/negotiations/{neg3}/respond", headers=tgt_auth, json={
            "decision": "accepted",
            "agreed_constraints": {"max_tokens": 1000},
        })
        print("accept:", r.status_code, r.json().get("status"), "session_token:", bool(r.json().get("session_token")))
        if r.status_code != 200 or r.json().get("status") != "accepted" or not r.json().get("session_token"):
            fails.append("accept")

        # 8. Detail includes rounds history
        r = client.get(f"/negotiations/{neg3}", headers=req_auth)
        data = r.json()
        print("detail rounds:", len(data.get("rounds", [])))
        if r.status_code != 200 or len(data.get("rounds", [])) < 2:
            fails.append("rounds history")

        # 9. Negotiation list + filter
        r = client.get("/negotiations?limit=10", headers=req_auth)
        print("list:", r.status_code, "total:", r.json().get("total"))
        if r.status_code != 200 or r.json().get("total") < 3:
            fails.append("list")

        r = client.get("/negotiations?status=accepted", headers=req_auth)
        print("list filtered accepted:", r.status_code, r.json().get("total"))
        if r.status_code != 200 or r.json().get("total") < 1:
            fails.append("list filter")

        # 10. Auto-expiry (ttl=1s)
        r = client.post("/negotiations", headers=req_auth, json={
            **proposal_body(tgt_id), "ttl_seconds": 1,
        })
        neg4 = r.json()["negotiation_id"]
        time.sleep(2)
        r = client.post(f"/negotiations/{neg4}/respond", headers=tgt_auth, json={"decision": "accepted"})
        print("expired respond (expect 400):", r.status_code, r.json().get("detail", "")[:60])
        if r.status_code != 400:
            fails.append("auto-expiry")

        # 11. Terminal status cannot re-transition
        r = client.post(f"/negotiations/{neg3}/respond", headers=tgt_auth, json={"decision": "countered"})
        print("accepted->countered (expect 400):", r.status_code, r.json().get("detail", "")[:60])
        if r.status_code != 400:
            fails.append("terminal transition")

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
