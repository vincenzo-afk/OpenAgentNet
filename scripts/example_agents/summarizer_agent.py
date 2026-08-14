#!/usr/bin/env python3
"""Summarizer agent example for OpenAgentNet.

Registers itself with the network, polls its inbox for summarization tasks,
and returns a trivial extractive summary (keeps the first two sentences).
Real deployments would plug in an LLM here; the network contract stays the
same, which is the whole point of OpenAgentNet.

Run against a local stack::

    python3 summarizer_agent.py --base-url http://localhost:8000/v1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import re
import sys

import httpx

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
from sdk.oan import Agent, Capability  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("summarizer-agent")


def summarize(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:2])


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAgentNet summarizer agent")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--name", default="summarizer-agent")
    parser.add_argument("--interval", type=int, default=5, help="poll interval in seconds")
    args = parser.parse_args()

    agent = Agent(
        base_url=args.base_url,
        name=args.name,
        display_name="Summarizer Agent",
        description="Trivial extractive summarizer. Reference implementation agent.",
        capabilities=[
            Capability(
                name="summarization",
                description="Summarizes long text by keeping the first two sentences",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
                tags=["llm", "text", "summarization"],
            ),
            Capability(
                name="text-processing",
                description="General text processing",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
                tags=["text"],
            ),
        ],
        endpoint="http://localhost:8000/agent/execute/summarizer",
        owner_name="openagentnet-example",
    )

    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        reg = agent.register()
        log.info("Registered %s (did=%s)", agent.did, agent.did)

        step = 0
        while True:
            step += 1
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
                        summary = summarize(text)
                        log.info("Processing %s: %d chars -> %d chars", msg_id, len(text), len(summary))
                        agent.report_result(
                            message_id=msg_id,
                            success=True,
                            execution_ms=random.randint(10, 200),
                            result={"summary": summary},
                        )
            except Exception:  # noqa: BLE001
                log.exception("inbox poll failed")

            log.info("idle (%d polls)", step)
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(args.interval))

    return 0


if __name__ == "__main__":
    sys.exit(main())
