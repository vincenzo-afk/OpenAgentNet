"""Phase 4 verification: workflow DAG validation + orchestration dispatch engine.

Sets up a local fake agent HTTP endpoint that accepts dispatched tasks and
auto-reports results via POST /v1/messages/{id}/result, so the engine can
actually execute a 3-step pipeline end to end.
"""
from __future__ import annotations

import base64
import os
import json
import random
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

BASE = "http://localhost:8000/v1"
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILED.append(name)


def encode_canonical_json(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


class FakeAgentHandler(BaseHTTPRequestHandler):
    """Fake agent executor: completes every dispatched task as success."""

    def log_message(self, *_args) -> None:
        pass
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"alive": true}')
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        task = body.get("task")
        node = body.get("payload", {}).get("workflow_node", "unknown")
        result_payload = {"summary": f"fake-{task}-result-for-{node}"}
        # Report result back asynchronously
        threading.Thread(
            target=self._report, args=(body.get("message_id"), result_payload), daemon=True
        ).start()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"accepted": True}).encode())

    def _report(self, message_id: str | None, payload: dict) -> None:
        if not message_id:
            return
        time.sleep(0.3)
        try:
            requests.post(
                f"{BASE}/messages/{message_id}/result",
                json={"status": "success", "result": payload, "execution_ms": 12},
                headers={"Authorization": f"Bearer {FAKE_AGENT_TOKEN}"},
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            pass


FAKE_AGENT_TOKEN = ""
FAKE_AGENT_ID = ""


def register_fake_agent(client: requests.Session) -> tuple[str, str]:
    """Register an agent whose endpoint is our local fake executor."""
    import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519
    from cryptography.hazmat.primitives import serialization

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    capabilities = [
        {
            "name": "summarization",
            "description": "Fake summarizer for pipeline tests",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "tags": [],
            "latency_estimate_ms": None,
            "cost_estimate": None,
        }
    ]
    manifest = {
        "protocol_version": "0.1.0",
        "name": f"phase4-fake-agent-{random.randbytes(3).hex()}",
        "display_name": None,
        "version": "0.4.0",
        "description": "Fake agent for Phase 4 orchestration tests",
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": "Phase4 Test"},
        "capabilities": capabilities,
        "endpoint": "http://localhost:9444",
        "health_endpoint": None,
        "public_key": base64.b64encode(public_bytes).decode(),
        "permissions_required": [],
        "permissions_offered": [],
        "tags": ["phase4"],
        "metadata": {},
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = private_key.sign(encode_canonical_json(manifest) + timestamp.encode())
    proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}
    resp = client.post(f"{BASE}/agents/register", json={"identity": manifest, "proof": proof})
    if resp.status_code != 201:
        print("register fake agent failed:", resp.status_code, resp.text[:300])
        sys.exit(1)
    data = resp.json()
    return str(data["agent_id"]), str(data["api_token"])


def main() -> None:
    global FAKE_AGENT_TOKEN, FAKE_AGENT_ID

    client = requests.Session()

    # 1. Start the fake agent HTTP server (skipped if an external fake server
    #    is already bound to 9444 via OAN_SKIP_SERVER=1)
    if os.environ.get("OAN_SKIP_SERVER") != "1":
        server = ThreadingHTTPServer(("localhost", 9444), FakeAgentHandler)
        server.socket.listen(256)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    else:
        server = None  # external long-lived fake server assumed

    # 2. Register the fake agent (summarization capability)
    FAKE_AGENT_ID, FAKE_AGENT_TOKEN = register_fake_agent(client)
    check("fake agent registration", True, FAKE_AGENT_ID[:8])

    # Expose the API token so an external long-lived fake server (OAN_SKIP_SERVER=1)
    # can auto-report task results back to the platform.
    with open("/tmp/oan_fake_token", "w") as fh:
        fh.write(FAKE_AGENT_TOKEN)

    # Heartbeat the fake agent so it is considered active for host resolution
    hb = client.post(
        f"{BASE}/agents/{FAKE_AGENT_ID}/heartbeat",
        json={},
        headers={"Authorization": f"Bearer {FAKE_AGENT_TOKEN}"},
    )
    check("fake agent heartbeat", hb.status_code == 200, f"status={hb.status_code}")

    # 3. Register an owner agent for the workflows
    import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519_owner
    from cryptography.hazmat.primitives import serialization as ser_owner

    owner_key = ed25519_owner.Ed25519PrivateKey.generate()
    owner_public = owner_key.public_key().public_bytes(
        ser_owner.Encoding.Raw, ser_owner.PublicFormat.Raw
    )
    owner_manifest = {
        "protocol_version": "0.1.0",
        "name": f"phase4-owner-{random.randbytes(3).hex()}",
        "display_name": None,
        "version": "0.4.0",
        "description": "Workflow owner for Phase 4 tests",
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": "Phase4 Owner"},
        "capabilities": [
            {
                "name": "delegate:workflow",
                "description": "Workflow orchestration scope",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "tags": [],
                "latency_estimate_ms": None,
                "cost_estimate": None,
            }
        ],
        "endpoint": "http://localhost:9444",
        "health_endpoint": None,
        "public_key": base64.b64encode(owner_public).decode(),
        "permissions_required": [],
        "permissions_offered": [],
        "tags": ["phase4"],
        "metadata": {},
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = owner_key.sign(encode_canonical_json(owner_manifest) + timestamp.encode())
    proof = {"timestamp": timestamp, "signature": base64.urlsafe_b64encode(signature).decode()}
    resp = client.post(f"{BASE}/agents/register", json={"identity": owner_manifest, "proof": proof})
    check("owner agent registration", resp.status_code == 201)
    owner_id = resp.json().get("agent_id")
    owner_token = resp.json().get("api_token")
    owner_auth = {"Authorization": f"Bearer {owner_token}"}

    # 4. DAG validation: invalid definitions must be rejected with 400
    invalid_defs = {
        "cycle": {
            "tasks": [
                {"id": "a", "agent_capability": "summarization", "depends_on": ["b"]},
                {"id": "b", "agent_capability": "summarization", "depends_on": ["a"]},
            ]
        },
        "duplicate": {
            "tasks": [
                {"id": "x", "agent_capability": "summarization"},
                {"id": "x", "agent_capability": "summarization"},
            ]
        },
        "undefined_dep": {
            "tasks": [
                {"id": "a", "agent_capability": "summarization", "depends_on": ["missing"]},
            ]
        },
    }
    for case, definition in invalid_defs.items():
        resp = client.post(
            f"{BASE}/workflows",
            headers=owner_auth,
            json={"name": f"invalid-{case}", "definition": definition},
        )
        check(f"dag validation rejects {case}", resp.status_code == 400, resp.text[:80])

    # 5. Valid 3-agent pipeline: fetch -> summarize -> publish
    definition = {
        "context": {"subject": "phase4"},
        "tasks": [
            {"id": "fetch", "agent_capability": "summarization", "depends_on": [], "payload": {"text": "input"}},
            {"id": "summarize", "agent_capability": "summarization", "depends_on": ["fetch"], "payload": {"text": "s1"}},
            {"id": "publish", "agent_capability": "summarization", "depends_on": ["summarize"], "payload": {"text": "s2"}},
        ],
    }
    resp = client.post(f"{BASE}/workflows", headers=owner_auth, json={"name": "phase4-pipeline", "definition": definition})
    check("workflow create (valid DAG)", resp.status_code == 201)
    wf_id = resp.json().get("workflow_id") if resp.status_code == 201 else None

    if wf_id:
        # 6. Wait for the engine to execute steps topologically
        deadline = time.time() + 150
        final = None
        fake_server_down_reported = False
        while time.time() < deadline:
            try:
                alive = requests.get("http://localhost:9444/", timeout=2).status_code == 200
            except Exception:
                alive = False
            if not alive and not fake_server_down_reported:
                if os.environ.get("OAN_SKIP_SERVER") != "1":
                    print("[WARN] fake agent server on 9444 is DOWN", flush=True)
                fake_server_down_reported = True
            resp = client.get(f"{BASE}/workflows/{wf_id}", headers=owner_auth)
            if resp.status_code == 200:
                wf = resp.json()
                if wf["status"] in ("success", "partial", "failed", "cancelled"):
                    final = wf
                    break
            time.sleep(1)
        check("workflow dispatch completes", final is not None, final["status"] if final else "not found")
        if final:
            check(
                "pipeline ran topologically (fetch->summarize->publish)",
                [t["node_id"] for t in final["tasks"]] == ["fetch", "summarize", "publish"],
            )
            for t in final["tasks"]:
                check(
                    f"step {t['node_id']} succeeded",
                    t["status"] == "success",
                    t["status"],
                )

    # 7. Failure cascade: step 'fail-step' will be reported failed by...
    # Simpler: create workflow whose host disappears — create workflow targeting
    # a capability nobody has, expecting the engine to mark it failed/partial.
    resp = client.post(
        f"{BASE}/workflows",
        headers=owner_auth,
        json={
            "name": "no-host-pipeline",
            "definition": {
                "tasks": [
                    {"id": "mystery", "agent_capability": "quantum-synthesis", "depends_on": []},
                    {"id": "after", "agent_capability": "quantum-synthesis", "depends_on": ["mystery"]},
                ]
            },
        },
    )
    check("workflow create (no host capability)", resp.status_code == 201)
    wf2_id = resp.json().get("workflow_id") if resp.status_code == 201 else None
    if wf2_id:
        final2 = None
        deadline = time.time() + 150
        while time.time() < deadline:
            resp = client.get(f"{BASE}/workflows/{wf2_id}", headers=owner_auth)
            if resp.status_code == 200:
                wf = resp.json()
                if wf["status"] in ("partial", "failed", "cancelled"):
                    final2 = wf
                    break
            time.sleep(1)
        check("no-host workflow terminates as failed/partial", final2 is not None, final2["status"] if final2 else "unknown")

    # 8. List workflows
    resp = client.get(f"{BASE}/workflows?limit=10", headers=owner_auth)
    check("workflow list", resp.status_code == 200, f"total={resp.json().get('total')}")

    # 9. Workflow NATS events published — replay the OAN_EVENTS stream and
    # count workflow-related messages that were published during this run.
    try:
        import asyncio
        from nats.aio.client import Client as _NATSClient

        async def grab() -> int:
            nc = _NATSClient()
            await nc.connect("nats://localhost:4222", connect_timeout=5)
            js = nc.jetstream()
            info = await js.stream_info("OAN_EVENTS")
            total = info.state.messages
            if total == 0:
                await nc.close()
                return 0
            # Attach an ephemeral consumer and pull a batch for replay.
            pull = await js.pull_subscribe(
                "oan.events.>",
                "eph-check-phase4",
                stream="OAN_EVENTS",
            )
            batch = await pull.fetch(min(total, 50), timeout=5)
            count = sum(
                1 for m in batch if b'"workflow"' in m.data or b'workflow' in m.data[:200]
            )
            for m in batch:
                try:
                    await m.ack()
                except Exception:
                    pass
            await nc.close()
            return count

        events = asyncio.run(asyncio.wait_for(grab(), timeout=20))
        check("workflow NATS events emitted", events >= 3, f"{events} workflow events")
    except Exception as exc:  # noqa: BLE001
        check("workflow NATS events emitted", False, str(exc)[:150])

    if server:
        server.shutdown()
    print("\n=== RESULT ===")
    if FAILED:
        print(f"FAILED: {FAILED}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
