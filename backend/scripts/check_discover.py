#!/usr/bin/env python3
"""Verify discovery works for the seeded demo agents."""
from __future__ import annotations

import httpx

TOKEN = None
with open("/tmp/demo_token.txt") as f:
    TOKEN = f.read().strip()

with httpx.Client(base_url="http://localhost:8000/v1", timeout=15) as client:
    resp = client.get("/discover?capability=summarization",
                      headers={"Authorization": f"Bearer {TOKEN}"})
    print("status:", resp.status_code)
    data = resp.json()
    print(data)
