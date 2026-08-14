export interface AgentSummary {
  agent_id: string;
  did: string;
  name: string;
  display_name?: string | null;
  version: string;
  description?: string | null;
  capabilities: string[];
  tags: string[];
  status: string;
  trust_score: number;
  metadata: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface Message {
  id: string;
  message_id?: string;
  from_agent_id: string;
  to_agent_id: string;
  type: string;
  capability_name?: string | null;
  payload: Record<string, unknown> | null;
  status: string;
  created_at: string;
  ttl_seconds?: number | null;
}

export interface TrustScore {
  agent_id: string;
  score: number;
  components: {
    task_completion_rate: number;
    latency_adherence: number;
    dispute_outcome: number;
    age_factor: number;
  };
  total_tasks: number;
  successful_tasks: number;
  dispute_count: number;
  last_active: string | null;
}

export interface MarketplaceListing {
  id: string;
  agent_id: string;
  title: string;
  long_description?: string | null;
  pricing: { currency: string; unit_price: number; unit: string };
  is_public: boolean;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://localhost:8000/v1";

function authHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export async function fetchAgents(token: string | null): Promise<AgentSummary[]> {
  const resp = await fetch(`${BASE_URL}/discover?limit=100`, {
    headers: authHeaders(token),
    next: { revalidate: 10 },
  });
  if (!resp.ok) throw new Error(`discover failed: ${resp.status}`);
  const data = (await resp.json()) as { agents: AgentSummary[] };
  return data.agents || [];
}

export async function fetchAgentDetail(agentId: string, token: string | null): Promise<AgentSummary | null> {
  const resp = await fetch(`${BASE_URL}/agents/${agentId}`, {
    headers: authHeaders(token),
    next: { revalidate: 5 },
  });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`agent detail failed: ${resp.status}`);
  return (await resp.json()) as AgentSummary;
}

export async function fetchTrust(agentId: string, token: string | null): Promise<TrustScore | null> {
  const resp = await fetch(`${BASE_URL}/trust/${agentId}`, {
    headers: authHeaders(token),
    next: { revalidate: 10 },
  });
  if (!resp.ok) return null;
  return (await resp.json()) as TrustScore;
}

export async function fetchMessages(agentId: string, token: string | null): Promise<Message[]> {
  const resp = await fetch(`${BASE_URL}/messages?limit=50`, {
    headers: authHeaders(token),
    next: { revalidate: 5 },
  });
  if (!resp.ok) return [];
  const data = (await resp.json()) as { messages: Message[] } | { items: Message[] };
  return (data as { messages?: Message[] }).messages || (data as { items?: Message[] }).items || [];
}

export async function fetchListings(token: string | null): Promise<MarketplaceListing[]> {
  const resp = await fetch(`${BASE_URL}/marketplace/listings`, {
    headers: authHeaders(token),
    next: { revalidate: 10 },
  });
  if (!resp.ok) return [];
  const data = (await resp.json()) as { listings: MarketplaceListing[] } | { items: MarketplaceListing[] };
  return (data as { listings?: MarketplaceListing[] }).listings || (data as { items?: MarketplaceListing[] }).items || [];
}

export async function sendTask(
  fromAgentId: string,
  toDid: string,
  capability: string,
  payload: Record<string, unknown>,
  token: string | null,
): Promise<{ message_id: string; status: string }> {
  const resp = await fetch(`${BASE_URL}/tasks`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      executor_id: toDid.replace("did:oan:", ""),
      capability_slug: capability,
      payload,
      ttl_seconds: 300,
    }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`send task failed: ${resp.status} ${err}`);
  }
  return (await resp.json()) as { message_id: string; status: string };
}
