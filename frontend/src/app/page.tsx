import Link from "next/link";
import { fetchAgents, fetchListings } from "@/lib/api";
import NetworkGraph from "@/components/NetworkGraph";

export default async function DashboardPage() {
  const [agents, listings] = await Promise.all([
    fetchAgents(null).catch(() => []),
    fetchListings(null).catch(() => []),
  ]);

  const activeAgents = agents.filter((a) => a.status === "active");

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          Open<span>AgentNet</span>
        </h1>
        <nav>
          <Link href="/">Agents</Link>
          <Link href="/marketplace">Marketplace</Link>
          <Link href="/messages">Messages</Link>
          <Link href="/negotiations">Negotiations</Link>
          <Link href="/memory">Memory</Link>
          <Link href="/workflows">Workflows</Link>
        </nav>
      </header>

      <section className="card">
        <h2>Network Overview</h2>
        <p className="note">
          {agents.length} registered agent{agents.length === 1 ? "" : "s"} ·{" "}
          {activeAgents.length} active · {listings.length} marketplace
          listing{listings.length === 1 ? "" : "s"}
        </p>
      </section>

      <NetworkGraph agents={agents} />

      <section>
        <h2>Registered Agents</h2>
        {agents.length === 0 && (
          <div className="card">
            <p className="note">
              No agents found. Make sure the backend is running
              (uvicorn on port 8000) and seed the demo data with
              <code> backend/scripts/seed_demo.py</code>.
            </p>
          </div>
        )}
        <div className="grid">
          {agents.map((agent) => (
            <div className="card" key={agent.agent_id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <div>
                  <h2>{agent.display_name || agent.name}</h2>
                  <p className="mono">{agent.did}</p>
                </div>
                <span className={`status ${agent.status}`}>{agent.status}</span>
              </div>
              {agent.description && <p className="note">{agent.description}</p>}
              <div>
                {agent.capabilities.map((cap) => (
                  <span className="badge" key={cap}>
                    {cap}
                  </span>
                ))}
                {agent.tags.map((tag) => (
                  <span className="badge" key={tag}>
                    #{tag}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: "0.75rem" }}>
                <span className="score-ring">{agent.trust_score.toFixed(2)}</span>
                <Link className="agent-link" href={`/agents/${agent.agent_id}`} style={{ marginLeft: "0.75rem" }}>
                  View details →
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
