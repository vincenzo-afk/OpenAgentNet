#!/usr/bin/env python3
"""Phase 2 verification: trust scoring, disputes, review queue, timeline."""
from __future__ import annotations

import os

import httpx

BASE = "http://localhost:8000/v1"


def seed_pair() -> tuple[str, str, str]:
    """Register two agents via the demo seed script and return (echo_id, summ_id, summ_token)."""
    import subprocess
    subprocess.run(
        ["python3", "scripts/seed_demo.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
        check=True, capture_output=True,
    )
    token = open("/tmp/demo_token.txt").read().strip()
    auth = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE, timeout=15) as client:
        echo_agents = client.get("/discover?capability=echo", headers=auth).json()["agents"]
        summ_agents = client.get("/discover?capability=summarization",
                                 headers=auth).json()["agents"]
    # seed_demo registers demo-echo + demo-summarizer (multiple runs may duplicate).
    # The saved token belongs to the newest summarizer; discover returns agents
    # newest-first, so the first matching entry of each capability pairs with it.
    echo = next(a for a in echo_agents if a["name"] == "demo-echo")
    summ = next(a for a in summ_agents if a["name"] == "demo-summarizer")
    return echo["agent_id"], summ["agent_id"], token


def main() -> int:
    echo_id, summ_id, token = seed_pair()
    auth = {"Authorization": f"Bearer {token}"}
    fails = []

    with httpx.Client(base_url=BASE, timeout=20) as client:
        # 1. Trust record exists with components
        r = client.get(f"/trust/{summ_id}", headers=auth)
        print("trust record:", r.status_code)
        if r.status_code != 200:
            fails.append("trust get")
        else:
            comps = r.json().get("components", {})
            for key in ("task_completion_rate", "endorsement_score", "dispute_penalty", "age_factor"):
                if key not in comps:
                    fails.append(f"missing component {key}")
            print("  components:", {k: round(v, 3) for k, v in comps.items()})

        # 2. Endorsement from echo -> summarizer (weight based on endorser trust)
        r = client.post("/trust/endorse", headers=auth, json={
            "to_agent_id": summ_id, "capability": "summarization",
            "comment": "reliable summarizer",
        })
        print("endorse:", r.status_code, r.text[:100])
        if r.status_code != 201:
            fails.append("endorse")

        # 3. Duplicate endorsement rejected
        r = client.post("/trust/endorse", headers=auth, json={
            "to_agent_id": summ_id, "capability": "summarization",
        })
        print("endorse dup (expect 400):", r.status_code)
        if r.status_code != 400:
            fails.append("endorse dup")

        # 4. Dispute submission
        r = client.post("/trust/disputes", headers=auth, json={
            "reported_agent_id": summ_id, "reason": "slow responses",
        })
        print("dispute create:", r.status_code)
        dispute_id = r.json().get("id")
        if r.status_code != 201:
            fails.append("dispute create")

        # 5. Dispute list (admin scope)
        r = client.get("/trust/disputes", headers=auth)
        print("disputes list:", r.status_code)
        if r.status_code != 200:
            fails.append("disputes list")
        else:
            print("  open disputes:", r.json()["total"])

        # 6. Mark under review
        r = client.post(f"/trust/disputes/{dispute_id}/mark-review", headers=auth)
        print("mark-review:", r.status_code, r.json().get("status"))
        if r.status_code != 200 or r.json().get("status") != "under_review":
            fails.append("mark-review")

        # 7. Resolve without operator secret -> 401
        r = client.post(f"/trust/disputes/{dispute_id}/resolve", headers=auth,
                        json={"verdict": "valid"})
        print("resolve no-secret (expect 401):", r.status_code)
        if r.status_code != 401:
            fails.append("resolve no-secret")

        # 8. Resolve with secret -> penalty applied
        r = client.post(
            f"/trust/disputes/{dispute_id}/resolve",
            headers={**auth, "X-Operator-Secret": os.environ.get("OPERATOR_SECRET", "")},
            json={"verdict": "valid", "resolution_notes": "confirmed"},
        )
        print("resolve:", r.status_code, r.json().get("status"))
        if r.status_code != 200 or r.json().get("status") != "resolved_valid":
            fails.append("resolve")

        # 9. Trust record reflects penalty
        r = client.get(f"/trust/{summ_id}", headers=auth)
        comps = r.json()["components"]
        print("  dispute_penalty after valid verdict:", comps.get("dispute_penalty"))
        if not comps.get("dispute_penalty"):
            fails.append("penalty not applied")

        # 10. Trust timeline
        r = client.get(f"/trust/{summ_id}/events", headers=auth)
        print("events:", r.status_code, len(r.json().get("events", [])))
        types = [e["event_type"] for e in r.json().get("events", [])]
        if "dispute_filed" not in types or "dispute_resolved" not in types:
            fails.append("timeline events")

        # 11. Endorsement ring anomaly: mutual endorsements
        r = client.post("/trust/endorse", headers=auth, json={
            "to_agent_id": echo_id, "capability": "echo",
            "comment": "reciprocal",
        })
        print("mutual endorse:", r.status_code)
        r = client.get(f"/trust/{echo_id}/events", headers=auth)
        types = [e["event_type"] for e in r.json().get("events", [])]
        print("  anomaly events:", [t for t in types if t.startswith("anomaly") or "ring" in t])

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
