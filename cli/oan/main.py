from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import Any

from openagentnet import OpenAgentNetClient, OpenAgentNetError


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _payload(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("payload must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oan", description="OpenAgentNet command-line client")
    parser.add_argument("--base-url", default=os.getenv("OAN_BASE_URL", "http://localhost:8000/v1"))
    parser.add_argument("--token", default=os.getenv("OAN_TOKEN"))
    commands = parser.add_subparsers(dest="command", required=True)

    discover = commands.add_parser("discover", help="find registered agents")
    discover.add_argument("--capability")
    discover.add_argument("--region")
    discover.add_argument("--tag", action="append", dest="tags")
    discover.add_argument("--min-trust-score", type=float)
    discover.add_argument("--limit", type=int, default=10)

    route = commands.add_parser("route", help="select an agent for a task")
    route.add_argument("description")
    route.add_argument("--capability", action="append", dest="capabilities", default=[])
    route.add_argument("--region")
    route.add_argument("--limit", type=int, default=5)

    task = commands.add_parser("task", help="work with tasks")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    send = task_commands.add_parser("send")
    send.add_argument("executor_id")
    send.add_argument("capability")
    send.add_argument("payload", help="JSON object")
    send.add_argument("--ttl-seconds", type=int, default=60)
    send.add_argument("--constraints", default="{}", help="JSON object")
    send.add_argument("--contract-id", help="accepted negotiation contract identifier")
    get = task_commands.add_parser("get")
    get.add_argument("task_id")
    stream = task_commands.add_parser("stream")
    stream.add_argument("task_id")

    agent = commands.add_parser("agent", help="inspect agent history")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    versions = agent_commands.add_parser("versions")
    versions.add_argument("agent_id")
    versions.add_argument("--limit", type=int, default=50)
    diff = agent_commands.add_parser("diff")
    diff.add_argument("agent_id")
    diff.add_argument("from_revision", type=int)
    diff.add_argument("to_revision", type=int)

    proof = commands.add_parser("proof", help="verify a privacy-preserving task proof")
    proof_commands = proof.add_subparsers(dest="proof_command", required=True)
    verify = proof_commands.add_parser("verify")
    verify.add_argument("task_id")
    return parser


def run(args: argparse.Namespace) -> int:
    with OpenAgentNetClient(args.base_url, token=args.token) as client:
        if args.command == "discover":
            print(_json(client.discover(
                args.capability,
                region=args.region,
                tags=args.tags,
                min_trust_score=args.min_trust_score,
                limit=args.limit,
            )))
        elif args.command == "route":
            print(_json(client.route_task(
                args.description,
                args.capabilities,
                constraints={"region": args.region} if args.region else {},
                limit=args.limit,
            )))
        elif args.command == "task":
            if args.task_command == "send":
                print(_json(client.send_task(
                    args.executor_id,
                    args.capability,
                    _payload(args.payload),
                    constraints=_payload(args.constraints),
                    ttl_seconds=args.ttl_seconds,
                    contract_id=args.contract_id,
                )))
            elif args.task_command == "get":
                print(_json(client.get_task(args.task_id)))
            elif args.task_command == "stream":
                for event in client.stream_task_chunks(args.task_id):
                    print(_json(event), flush=True)
        elif args.command == "agent":
            if args.agent_command == "versions":
                print(_json(client.list_agent_versions(args.agent_id, limit=args.limit)))
            else:
                print(_json(client.diff_agent_versions(args.agent_id, args.from_revision, args.to_revision)))
        elif args.command == "proof" and args.proof_command == "verify":
            print(_json(client.verify_privacy_proof(args.task_id)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OpenAgentNetError, ValueError, json.JSONDecodeError) as exc:
        print(f"oan: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
