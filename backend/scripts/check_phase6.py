#!/usr/bin/env python3
"""OpenAgentNet Phase 6 (Marketplace depth) verification.

Checks:
 1. Create marketplace listing (default access_tier = free)
 2. Listing response includes access_tier / tier_details
 3. Set access tier to 'paid' (owner only)
 4. Set access tier to 'invite_only' with tier_details
 5. Non-owner cannot change tier (403)
 6. Invalid access tier rejected (400)
 7. Search filter by access_tier
 8. Billing webhook records usage (metering shows calls)
 9. Metering filtered by agent
10. NATS events: marketplace.tier_changed / marketplace.usage emitted
"""
from __future__ import annotations

import asyncio
import base64
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import requests
from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from nats.aio.client import Client as NATS

BASE = "http://localhost:8000/v1"
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILED.append(name)


def register_agent(name_prefix: str) -> tuple[str, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manifest = {
        "protocol_version": "0.1.0",
        "name": f"{name_prefix}-{random.randbytes(3).hex()}",
        "display_name": None,
        "version": "1.0.0",
        "description": f"Phase 6 check agent ({name_prefix})",
        "owner": {"id": str(uuid.uuid4()), "type": "user", "name": name_prefix},
        "capabilities": [{"name": "summarization", "description": "Text summarization", "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "tags": [], "cost_estimate": None, "latency_estimate_ms": None}],
        "endpoint": f"http://localhost:8000/agent/execute/{name_prefix}",
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
    proof = {
        "timestamp": timestamp,
        "signature": "base64url:" + base64.urlsafe_b64encode(signature).decode(),
    }
    with requests.Session() as client:
        resp = client.post(
            f"{BASE}/agents/register",
            json={"identity": manifest, "proof": proof},
            timeout=15,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"register failed: {resp.status_code} {resp.text[:300]}")
        reg = resp.json()
        client.post(
            f"{BASE}/agents/{reg['agent_id']}/heartbeat",
            json={},
            headers={"Authorization": f"Bearer {reg['api_token']}"},
            timeout=15,
        )
    return reg["agent_id"], reg["api_token"]


def main() -> int:
    with requests.Session() as client:
        owner_id, owner_token = register_agent("phase6-owner")
        outsider_id, outsider_token = register_agent("phase6-outsider")
        owner_auth = {"Authorization": f"Bearer {owner_token}"}
        outsider_auth = {"Authorization": f"Bearer {outsider_token}"}

        # 1-2. Create listing, verify default tier + fields
        resp = client.post(
            f"{BASE}/marketplace/listings",
            headers=owner_auth,
            json={
                "title": "Phase 6 Summarizer",
                "long_description": "Summarization service for Phase 6 verification",
                "pricing": {"currency": "USD", "base_price": 0.01},
                "sla": {"avg_latency_seconds": 2.0},
                "tiers": [{"name": "basic", "rate_limit": 10}],
            },
            timeout=15,
        )
        check("create marketplace listing", resp.status_code == 201, f"status={resp.status_code}")
        listing = resp.json()
        listing_id = listing["id"]
        check(
            "listing has access_tier and tier_details",
            listing.get("access_tier") == "free" and isinstance(listing.get("tier_details"), dict),
            f"access_tier={listing.get('access_tier')}",
        )

        # 3-4. Tier updates
        r = client.put(
            f"{BASE}/marketplace/listings/{listing_id}/tier",
            headers=owner_auth,
            json={"access_tier": "paid", "tier_details": {"price_per_call": 0.01}},
            timeout=15,
        )
        check("set access tier to 'paid'", r.status_code == 200, f"status={r.status_code}")
        check("tier update reflects on listing", r.json().get("access_tier") == "paid")

        r = client.put(
            f"{BASE}/marketplace/listings/{listing_id}/tier",
            headers=owner_auth,
            json={
                "access_tier": "invite_only",
                "tier_details": {"allowed_agents": ["agent-1", "agent-2"]},
            },
            timeout=15,
        )
        check(
            "set access tier to 'invite_only' with details",
            r.status_code == 200 and r.json().get("tier_details", {}).get("allowed_agents")
            == ["agent-1", "agent-2"],
            f"status={r.status_code}",
        )

        # 5. Non-owner forbidden
        r = client.put(
            f"{BASE}/marketplace/listings/{listing_id}/tier",
            headers=outsider_auth,
            json={"access_tier": "free"},
            timeout=15,
        )
        check("non-owner tier change rejected (403)", r.status_code == 403, f"status={r.status_code}")

        # 6. Invalid tier rejected
        r = client.put(
            f"{BASE}/marketplace/listings/{listing_id}/tier",
            headers=owner_auth,
            json={"access_tier": "gold"},
            timeout=15,
        )
        check("invalid tier rejected (400)", r.status_code == 400, f"status={r.status_code}")

        # Reset to paid for search check
        client.put(
            f"{BASE}/marketplace/listings/{listing_id}/tier",
            headers=owner_auth,
            json={"access_tier": "paid"},
            timeout=15,
        )

        # 7. Search by access_tier
        r = client.get(f"{BASE}/marketplace/listings", params={"access_tier": "paid"}, timeout=15)
        paid = r.json()
        check(
            "search filter by access_tier",
            r.status_code == 200 and paid["total"] >= 1 and all(
                item["access_tier"] == "paid" for item in paid["items"]
            ),
            f"total={paid['total']}",
        )

        # 8. Billing webhook + metering
        consumer_id = outsider_id  # any agent consuming the listing
        r = client.post(
            f"{BASE}/marketplace/webhooks/billing",
            json={
                "listing_id": listing_id,
                "agent_id": consumer_id,
                "calls": 3,
                "event_type": "usage",
            },
            timeout=15,
        )
        check(
            "billing webhook accepts usage",
            r.status_code == 202 and r.json().get("calls") == 3 and r.json().get("accepted") is True,
            f"status={r.status_code} body={r.text[:120]}",
        )
        # Second call bumps to 6
        client.post(
            f"{BASE}/marketplace/webhooks/billing",
            json={"listing_id": listing_id, "agent_id": consumer_id, "calls": 3},
            timeout=15,
        )
        r = client.get(
            f"{BASE}/marketplace/listings/{listing_id}/metering",
            params={"agent_id": consumer_id},
            timeout=15,
        )
        meter = r.json()
        check(
            "metering tracks cumulative calls",
            r.status_code == 200 and meter["access_tier"] == "paid"
            and len(meter["items"]) == 1 and meter["items"][0]["calls"] == 6,
            f"calls={meter['items'][0]['calls'] if meter['items'] else 'none'}",
        )

        # 9. Metering filter by agent (empty for unknown)
        r = client.get(
            f"{BASE}/marketplace/listings/{listing_id}/metering",
            params={"agent_id": "00000000-0000-0000-0000-000000000000"},
            timeout=15,
        )
        check(
            "metering filtered by agent",
            r.status_code == 200 and r.json()["items"] == [],
            f"items={r.json()['items']}",
        )

    # 10. NATS events
    try:
        events = asyncio.run(asyncio.wait_for(collect_events(), timeout=25))
        check("marketplace NATS events emitted", events >= 3, f"{events} marketplace events")
    except Exception as exc:  # noqa: BLE001
        check("marketplace NATS events emitted", False, f"exception: {exc}")

    print("=== RESULT ===")
    if FAILED:
        print(f"FAILED: {FAILED}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


async def collect_events() -> int:
    nc = NATS()
    await nc.connect("nats://localhost:4222", connect_timeout=5)
    js = nc.jetstream()
    pull = await js.pull_subscribe("oan.events.marketplace.>", None, stream="OAN_EVENTS")
    await nc.flush(timeout=3)

    async def trigger() -> None:
        loop = asyncio.get_event_loop()
        owner_id, owner_token = await loop.run_in_executor(
            None, lambda: register_agent("phase6-nats")
        )
        with requests.Session() as client:
            owner_auth = {"Authorization": f"Bearer {owner_token}"}
            r = client.post(
                f"{BASE}/marketplace/listings",
                headers=owner_auth,
                json={"title": "NATS event test listing"},
                timeout=15,
            )
            if r.status_code != 201:
                raise RuntimeError(f"listing create failed: {r.status_code} {r.text[:200]}")
            lid = r.json()["id"]
            client.put(
                f"{BASE}/marketplace/listings/{lid}/tier",
                headers=owner_auth,
                json={"access_tier": "paid"},
                timeout=15,
            )
            client.post(
                f"{BASE}/marketplace/webhooks/billing",
                json={"listing_id": lid, "agent_id": owner_id, "calls": 1},
                timeout=15,
            )

    await trigger()
    await asyncio.sleep(1.5)

    events = 0
    try:
        batch = await pull.fetch(50, timeout=4)
        for m in batch:
            if m.subject.startswith("oan.events.marketplace."):
                events += 1
            try:
                await m.ack()
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        print("nats fetch err:", exc)
    await nc.close()
    return events


if __name__ == "__main__":
    sys.exit(main())
