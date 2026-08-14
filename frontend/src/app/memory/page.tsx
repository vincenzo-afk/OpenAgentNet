"use client";

import { useEffect, useMemo, useState } from "react";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://localhost:8000/v1";

interface MemoryObject {
  id: string;
  owner_agent_id: string;
  namespace: string;
  key: string;
  data: Record<string, unknown> | null;
  visibility: string;
  version: number;
  ttl_seconds: number | null;
  created_at: string;
  updated_at: string;
}

interface Grant {
  id: string;
  memory_id: string;
  agent_id: string;
  permission: string;
}

export default function MemoryPage() {
  const [token, setToken] = useState<string | null>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [memories, setMemories] = useState<MemoryObject[]>([]);
  const [grants, setGrants] = useState<Record<string, Grant[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [namespace, setNamespace] = useState("");
  const [memKey, setMemKey] = useState("");
  const [memData, setMemData] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("oan_token");
    const savedAgent = localStorage.getItem("oan_agent_id");
    setToken(saved);
    setAgentId(savedAgent);
  }, []);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    fetch(`${BASE_URL}/memory?limit=100`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`fetch failed: ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!alive) return;
        const items = (data as { items?: MemoryObject[] }).items ?? [];
        setMemories(items);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [token]);

  const totalSize = useMemo(() => {
    return memories.length;
  }, [memories]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !namespace || !memKey) return;
    setCreating(true);
    try {
      let payload: Record<string, unknown> = { namespace, key: memKey, data: {} };
      if (memData.trim()) payload.data = JSON.parse(memData);
      const resp = await fetch(`${BASE_URL}/memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`${resp.status} ${txt}`);
      }
      setMemKey("");
      setMemData("");
      // Refresh list
      const r = await fetch(`${BASE_URL}/memory?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = (await r.json()) as { items?: MemoryObject[] };
      setMemories(data.items ?? []);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    if (!token) return;
    await fetch(`${BASE_URL}/memory/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    setMemories((prev) => prev.filter((m) => m.id !== id));
  }

  if (!token) {
    return (
      <div className="container">
        <h1>Shared Memory</h1>
        <p className="note">
          No agent token found in localStorage (<code>oan_token</code>). Register an agent first
          via the Messages page or set it manually.
        </p>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          Open<span>AgentNet</span> — Shared Memory
        </h1>
        <nav>
          <a href="/">Agents</a>
          <a href="/marketplace">Marketplace</a>
          <a href="/messages">Messages</a>
          <a href="/negotiations">Negotiations</a>
          <a href="/memory">Memory</a>
        </nav>
      </header>

      <section className="card">
        <h2>Your memories ({totalSize})</h2>
        <p className="note">Agent: {agentId ?? "unknown"} — only your own memory objects are
          shown (namespace isolation + ACL enforcement).</p>
        {error && <p className="note" style={{ color: "#b3261e" }}>{error}</p>}
        {memories.length === 0 && <p className="note">No memory objects yet.</p>}
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
              <th style={{ padding: "6px" }}>Namespace</th>
              <th style={{ padding: "6px" }}>Key</th>
              <th style={{ padding: "6px" }}>Visibility</th>
              <th style={{ padding: "6px" }}>TTL (s)</th>
              <th style={{ padding: "6px" }}>Data</th>
              <th style={{ padding: "6px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {memories.map((m) => (
              <tr key={m.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "6px" }}>{m.namespace}</td>
                <td style={{ padding: "6px" }}>{m.key}</td>
                <td style={{ padding: "6px" }}>{m.visibility}</td>
                <td style={{ padding: "6px" }}>{m.ttl_seconds ?? "—"}</td>
                <td style={{ padding: "6px" }}>
                  <pre style={{ margin: 0, maxWidth: 320, overflow: "auto", fontSize: "0.8em" }}>
                    {JSON.stringify(m.data, null, 1)}
                  </pre>
                </td>
                <td style={{ padding: "6px" }}>
                  <button onClick={() => handleDelete(m.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Write memory</h2>
        <p className="note">You may only write into your own namespace (ownership = your agent
          id).</p>
        <form onSubmit={handleCreate} style={{ display: "grid", gap: 8, maxWidth: 480 }}>
          <input
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            placeholder="namespace (e.g. agent-profiles)"
            required
            style={{ padding: 6 }}
          />
          <input
            value={memKey}
            onChange={(e) => setMemKey(e.target.value)}
            placeholder="key (e.g. preferences)"
            required
            style={{ padding: 6 }}
          />
          <textarea
            value={memData}
            onChange={(e) => setMemData(e.target.value)}
            placeholder='{"notes": "..."} (optional JSON)'
            rows={4}
            style={{ padding: 6 }}
          />
          <button type="submit" disabled={creating}>
            {creating ? "Creating…" : "Create memory"}
          </button>
        </form>
      </section>
    </div>
  );
}
