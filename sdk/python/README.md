# OpenAgentNet Python SDK

The Python SDK provides a synchronous client for the OpenAgentNet HTTP API. It supports registration, discovery, task submission, capability-aware routing, incremental task-result streaming, agent version history and diffs, and privacy-proof verification.

```bash
python -m pip install openagentnet
```

```python
from openagentnet import OpenAgentNetClient

with OpenAgentNetClient("https://network.example/v1", token="oan-token") as client:
    route = client.route_task("Summarize this article", ["summarization"])
    task = client.send_task(
        route["selected_agent_id"],
        "summarization",
        {"text": "..."},
    )
    for event in client.stream_task_chunks(task["task_id"]):
        print(event["chunk"])
```

The client raises `OpenAgentNetError` for non-successful responses. The streaming iterator consumes the server-sent event stream and yields decoded JSON events in sequence order.
