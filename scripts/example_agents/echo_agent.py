#!/usr/bin/env python3
"""Echo agent example for OpenAgentNet.

Registers itself with the network, polls its inbox for tasks, and echoes
the received text back as a task result. Demonstrates the minimal lifecycle
of an OpenAgentNet agent: register -> heartbeat -> poll -> respond.

Run against a local stack::

    python3 echo_agent.py --base-url http://localhost:8000/v1

Requires: httpx, canonicaljson, cryptography  (plus ../sdk/oan.py on sys.path).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys

import httpx

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
from sdk.oan import Agent, Capability  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("echo-agent")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAgentNet echo agent")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--name", default="echo-agent")
    parser.add_argument("--interval", type=int, default=5, help="poll interval in seconds")
    args = parser.parse_args()

    agent = Agent(
        base_url=args.base_url,
        name=args.name,
        display_name="Echo Agent",
        description="Echoes any received text. Reference implementation agent.",
        capabilities=[
            Capability(
                name="echo",
                description="Returns the received text unchanged",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                tags=["utility", "echo"],
            )
        ],
        endpoint="http://localhost:8000/agent/execute/echo",
        owner_name="openagentnet-example",
    )

    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        reg = agent.register()
        log.info("Registered %s (did=%s)", agent.did, agent.did)

        step = 0
        while True:
            step += 1
            # Periodic heartbeat so the agent stays marked active.
            try:
                agent.heartbeat()
            except Exception:  # noqa: BLE001
                log.warning("heartbeat failed")

            try:
                resp = client.get("/messages", headers=agent._auth())  # noqa: SLF001
                if resp.status_code == 200:
                    for message in resp.json().get("messages", resp.json().get("items", [])):
                        msg_id = message.get("message_id") or message.get("id")
                        task = message.get("task") or message.get("payload") or {}
                        text = (task.get("payload") or {}).get("text", "")
                        log.info("Processing %s: echo '%s'", msg_id, text[:60])
                        agent.report_result(
                            message_id=msg_id,
                            success=True,
                            execution_ms=random.randint(1, 50),
                            result={"text": text},
                        )
            except Exception:  # noqa: BLE001
                log.exception("inbox poll failed")

            log.info("idle (%d polls)", step)
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(args.interval))

    return 0


if __name__ == "__main__":
    sys.exit(main())
