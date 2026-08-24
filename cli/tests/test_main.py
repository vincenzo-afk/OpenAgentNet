from __future__ import annotations

import json

import pytest

from oan.main import _payload, build_parser, run


def test_parser_supports_nested_task_commands() -> None:
    args = build_parser().parse_args(["task", "send", "agent-1", "echo", '{"text":"hi"}'])
    assert args.command == "task"
    assert args.task_command == "send"
    assert args.executor_id == "agent-1"
    contract_args = build_parser().parse_args([
        "task", "send", "agent-1", "echo", "{\"text\":\"hi\"}", "--contract-id", "contract-1"
    ])
    assert contract_args.contract_id == "contract-1"
    team_args = build_parser().parse_args([
        "team", "send", "team-1", "echo", "{\"text\":\"hi\"}", "--ttl-seconds", "30"
    ])
    assert team_args.team_command == "send"
    assert team_args.team_id == "team-1"
    assert team_args.ttl_seconds == 30


def test_payload_requires_json_object() -> None:
    with pytest.raises(ValueError):
        _payload("[1, 2]")


def test_route_command_prints_selected_agent(monkeypatch, capsys) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def route_task(self, description, capabilities, *, constraints, limit):
            assert description == "summarize"
            assert capabilities == ["summarization"]
            assert constraints == {"region": "eu"}
            assert limit == 2
            return {"selected_agent_id": "agent-1"}

    monkeypatch.setattr("oan.main.OpenAgentNetClient", FakeClient)
    args = build_parser().parse_args([
        "--base-url", "https://example.test/v1",
        "route", "summarize", "--capability", "summarization", "--region", "eu", "--limit", "2",
    ])
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["selected_agent_id"] == "agent-1"
