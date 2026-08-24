from __future__ import annotations

import httpx
import json
import pytest

from openagentnet import OpenAgentNetClient, OpenAgentNetError


def test_send_task_sends_bearer_auth_and_payload() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["json"] = request.read()
        return httpx.Response(201, json={"task_id": "t-1", "status": "pending"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = OpenAgentNetClient("https://example.test/v1", token="secret", client=http_client)
        result = client.send_task("agent-1", "echo", {"text": "hi"})

    assert result["task_id"] == "t-1"
    assert captured["authorization"] == "Bearer secret"
    assert json.loads(captured["json"])["capability_slug"] == "echo"


def test_send_task_forwards_contract_id() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.read())
        return httpx.Response(201, json={"task_id": "t-1", "status": "pending"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAgentNetClient(client=http_client)
        client.send_task("agent-1", "echo", {"text": "hi"}, contract_id="contract-1")

    assert captured["json"]["contract_id"] == "contract-1"


def test_stream_task_chunks_decodes_server_sent_events() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"sequence": 0, "chunk": {"text": "hi"}}\n\ndata: {"sequence": 1, "is_final": true}\n\n',
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAgentNetClient(client=http_client)
        events = list(client.stream_task_chunks("task-1"))

    assert events == [
        {"sequence": 0, "chunk": {"text": "hi"}},
        {"sequence": 1, "is_final": True},
    ]


def test_http_errors_raise_sdk_exception() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "missing"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAgentNetClient(client=http_client)
        with pytest.raises(OpenAgentNetError) as error:
            client.get_task("missing")

    assert error.value.status_code == 404
    assert error.value.detail == {"detail": "missing"}
