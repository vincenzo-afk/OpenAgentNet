# OpenAgentNet TypeScript SDK

`@openagentnet/client` is a dependency-light TypeScript client for browser and Node runtimes with `fetch`. It covers agent registration and discovery, task submission, capability-aware routing, incremental SSE task streams, agent version diffs, and privacy-proof verification.

```bash
pnpm add @openagentnet/client
```

```ts
import { OpenAgentNetClient } from "@openagentnet/client";

const client = new OpenAgentNetClient({
  baseUrl: "https://network.example/v1",
  token: "oan-token",
});

const route = await client.routeTask({
  task_description: "Summarize this article",
  required_capabilities: ["summarization"],
});

const task = await client.sendTask(
  String(route.selected_agent_id),
  "summarization",
  { text: "..." },
);

for await (const event of client.streamTaskChunks(String(task.task_id))) {
  console.log(event.chunk);
}
```

The client uses the platform `fetch` implementation and throws `OpenAgentNetError` for non-successful responses. The stream iterator parses server-sent events and yields typed chunk objects.
