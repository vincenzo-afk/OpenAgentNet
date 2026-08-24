export type JsonObject = Record<string, unknown>;

export interface OpenAgentNetClientOptions {
  baseUrl?: string;
  token?: string;
  fetchImpl?: typeof fetch;
}

export class OpenAgentNetError extends Error {
  readonly statusCode: number;
  readonly detail: unknown;

  constructor(statusCode: number, detail: unknown) {
    super(`OpenAgentNet request failed (${statusCode})`);
    this.name = "OpenAgentNetError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

export interface RoutingRequest {
  task_description: string;
  required_capabilities?: string[];
  constraints?: JsonObject;
  limit?: number;
}

export interface StreamChunk {
  task_id: string;
  sequence: number;
  chunk: JsonObject;
  is_final: boolean;
  created_at?: string;
}

export interface AgentVersion {
  agent_id: string;
  revision: number;
  version: string;
  endpoint: string;
  capabilities: JsonObject[];
  metadata: JsonObject;
  created_at: string;
}

export class OpenAgentNetClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: OpenAgentNetClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8000/v1").replace(/\/$/, "");
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, { ...init, headers });
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = await response.text();
      }
      throw new OpenAgentNetError(response.status, detail);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  register(identity: JsonObject, proof: JsonObject): Promise<JsonObject> {
    return this.request<JsonObject>("/agents/register", {
      method: "POST",
      body: JSON.stringify({ identity, proof }),
    });
  }

  getAgent(agentId: string): Promise<JsonObject> {
    return this.request<JsonObject>(`/agents/${encodeURIComponent(agentId)}`);
  }

  discover(options: {
    capability?: string;
    region?: string;
    tags?: string[];
    minTrustScore?: number;
    limit?: number;
    sort?: string;
  } = {}): Promise<JsonObject> {
    const params = new URLSearchParams();
    if (options.capability) params.set("capability", options.capability);
    if (options.region) params.set("region", options.region);
    if (options.tags?.length) params.set("tags", options.tags.join(","));
    if (options.minTrustScore !== undefined) params.set("min_trust_score", String(options.minTrustScore));
    params.set("limit", String(options.limit ?? 10));
    params.set("sort", options.sort ?? "trust_score:desc");
    return this.request<JsonObject>(`/discover?${params.toString()}`);
  }

  sendTask(
    executorId: string,
    capabilitySlug: string,
    payload: JsonObject,
    options: { constraints?: JsonObject; ttlSeconds?: number } = {},
  ): Promise<JsonObject> {
    return this.request<JsonObject>("/tasks", {
      method: "POST",
      body: JSON.stringify({
        executor_id: executorId,
        capability_slug: capabilitySlug,
        payload,
        constraints: options.constraints ?? {},
        ttl_seconds: options.ttlSeconds ?? 60,
      }),
    });
  }

  getTask(taskId: string): Promise<JsonObject> {
    return this.request<JsonObject>(`/tasks/${encodeURIComponent(taskId)}`);
  }

  routeTask(request: RoutingRequest): Promise<JsonObject> {
    return this.request<JsonObject>("/routing/route", {
      method: "POST",
      body: JSON.stringify({
        task_description: request.task_description,
        required_capabilities: request.required_capabilities ?? [],
        constraints: request.constraints ?? {},
        limit: request.limit ?? 5,
      }),
    });
  }

  appendStreamChunk(
    taskId: string,
    sequence: number,
    chunk: JsonObject,
    isFinal = false,
  ): Promise<StreamChunk> {
    return this.request<StreamChunk>(`/tasks/${encodeURIComponent(taskId)}/stream`, {
      method: "POST",
      body: JSON.stringify({ sequence, chunk, is_final: isFinal }),
    });
  }

  async *streamTaskChunks(taskId: string): AsyncGenerator<StreamChunk> {
    const headers = new Headers(this.token ? { Authorization: `Bearer ${this.token}` } : undefined);
    headers.set("Accept", "text/event-stream");
    const response = await this.fetchImpl(`${this.baseUrl}/tasks/${encodeURIComponent(taskId)}/stream`, {
      headers,
    });
    if (!response.ok) throw new OpenAgentNetError(response.status, await response.text());
    if (!response.body) throw new Error("OpenAgentNet stream response has no body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const parseEvent = (event: string): StreamChunk | undefined => {
      const data = event
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      return data ? (JSON.parse(data) as StreamChunk) : undefined;
    };

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const event = parseEvent(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) yield event;
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    const finalEvent = parseEvent(buffer.trim());
    if (finalEvent) yield finalEvent;
  }

  listAgentVersions(agentId: string, limit = 50): Promise<{ agent_id: string; total: number; items: AgentVersion[] }> {
    return this.request(`/agents/${encodeURIComponent(agentId)}/versions?limit=${limit}`);
  }

  diffAgentVersions(agentId: string, fromRevision: number, toRevision: number): Promise<JsonObject> {
    const params = new URLSearchParams({ from_revision: String(fromRevision), to_revision: String(toRevision) });
    return this.request<JsonObject>(`/agents/${encodeURIComponent(agentId)}/diff?${params.toString()}`);
  }

  createPrivacyProof(taskId: string, outcome: 0 | 1, nonce: string): Promise<JsonObject> {
    return this.request<JsonObject>(`/tasks/${encodeURIComponent(taskId)}/privacy-proof`, {
      method: "POST",
      body: JSON.stringify({ outcome, nonce }),
    });
  }

  verifyPrivacyProof(taskId: string): Promise<JsonObject> {
    return this.request<JsonObject>(`/tasks/${encodeURIComponent(taskId)}/privacy-proof/verify`);
  }
}
