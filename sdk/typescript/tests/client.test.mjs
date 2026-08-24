import assert from "node:assert/strict";
import test from "node:test";
import { OpenAgentNetClient, OpenAgentNetError } from "../dist/index.js";

function response(body, init = {}) {
  return new Response(body, init);
}

test("sends bearer auth and task JSON", async () => {
  let request;
  const client = new OpenAgentNetClient({
    baseUrl: "https://example.test/v1",
    token: "secret",
    fetchImpl: async (input, init) => {
      request = { input: String(input), init };
      return response(JSON.stringify({ task_id: "t-1" }), { status: 201, headers: { "content-type": "application/json" } });
    },
  });

  const result = await client.sendTask("agent-1", "echo", { text: "hi" });
  assert.equal(result.task_id, "t-1");
  assert.equal(request.init.headers.get("Authorization"), "Bearer secret");
  assert.equal(JSON.parse(request.init.body).capability_slug, "echo");
});

test("sends team task broadcasts with the team destination", async () => {
  let request;
  const client = new OpenAgentNetClient({
    baseUrl: "https://example.test/v1",
    fetchImpl: async (input, init) => {
      request = { input: String(input), init };
      return response(JSON.stringify({ broadcast_id: "b-1" }), { status: 202 });
    },
  });

  const result = await client.sendTeamTask("team-1", "echo", { text: "hi" });
  assert.equal(result.broadcast_id, "b-1");
  assert.equal(request.input, "https://example.test/v1/messages");
  assert.equal(JSON.parse(request.init.body).to, "team:team-1");
  assert.equal(JSON.parse(request.init.body).task.name, "echo");
});

test("decodes server-sent task chunks", async () => {
  const client = new OpenAgentNetClient({
    fetchImpl: async () => response(
      'data: {"sequence":0,"chunk":{"text":"hi"}}\n\ndata: {"sequence":1,"is_final":true}\n\n',
      { status: 200, headers: { "content-type": "text/event-stream" } },
    ),
  });
  const events = [];
  for await (const event of client.streamTaskChunks("task-1")) events.push(event);
  assert.deepEqual(events, [
    { sequence: 0, chunk: { text: "hi" } },
    { sequence: 1, is_final: true },
  ]);
});

test("converts failed responses into OpenAgentNetError", async () => {
  const client = new OpenAgentNetClient({ fetchImpl: async () => response(JSON.stringify({ detail: "missing" }), { status: 404 }) });
  await assert.rejects(() => client.getTask("missing"), (error) => {
    assert.ok(error instanceof OpenAgentNetError);
    assert.equal(error.statusCode, 404);
    return true;
  });
});
