import Link from "next/link";
import type { AgentSummary } from "@/lib/api";

type NodePosition = { x: number; y: number };

function nodeColor(agent: AgentSummary): string {
  if (agent.status === "active") return agent.trust_score >= 0.7 ? "#2d6a4f" : "#1f5fa3";
  if (agent.status === "suspended") return "#9b1c1c";
  return "#6b7280";
}

export default function NetworkGraph({ agents }: { agents: AgentSummary[] }) {
  const width = 900;
  const height = 390;
  const columns = Math.min(4, Math.max(1, agents.length));
  const positions = new Map<string, NodePosition>();

  agents.forEach((agent, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    positions.set(agent.agent_id, {
      x: 110 + column * ((width - 220) / Math.max(columns - 1, 1)),
      y: 80 + row * 125,
    });
  });

  const edges = agents.flatMap((source, sourceIndex) =>
    agents.slice(sourceIndex + 1).flatMap((target) => {
      const sourceCapabilities = new Set(source.capabilities);
      const shared = target.capabilities.find((capability) => sourceCapabilities.has(capability));
      if (!shared) return [];
      return [{ source, target, label: shared }];
    }),
  );

  return (
    <section className="card" aria-labelledby="network-graph-title">
      <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "baseline", flexWrap: "wrap" }}>
        <div>
          <h2 id="network-graph-title">Network Graph</h2>
          <p className="note">Connections show shared capabilities; node color reflects status and trust.</p>
        </div>
        <span className="note">{edges.length} connection{edges.length === 1 ? "" : "s"}</span>
      </div>
      {agents.length === 0 ? (
        <p className="note">Register agents to populate the network graph.</p>
      ) : (
        <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
          <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Agent network graph" style={{ width: "100%", minWidth: 520, height: "auto", background: "var(--surface, #f8fafc)", borderRadius: 8 }}>
            {edges.map(({ source, target, label }) => {
              const from = positions.get(source.agent_id);
              const to = positions.get(target.agent_id);
              if (!from || !to) return null;
              return (
                <g key={`${source.agent_id}-${target.agent_id}`}>
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#94a3b8" strokeWidth="2" />
                  <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 6} textAnchor="middle" fontSize="11" fill="#64748b">{label}</text>
                </g>
              );
            })}
            {agents.map((agent) => {
              const position = positions.get(agent.agent_id);
              if (!position) return null;
              return (
                <Link href={`/agents/${agent.agent_id}`} key={agent.agent_id}>
                  <g role="link" aria-label={`View ${agent.display_name || agent.name}`}>
                    <circle cx={position.x} cy={position.y} r="31" fill={nodeColor(agent)} stroke="#ffffff" strokeWidth="3" />
                    <text x={position.x} y={position.y - 3} textAnchor="middle" fontSize="11" fill="#ffffff" fontWeight="600">{(agent.display_name || agent.name).slice(0, 13)}</text>
                    <text x={position.x} y={position.y + 12} textAnchor="middle" fontSize="10" fill="#ffffff">{agent.trust_score.toFixed(2)}</text>
                  </g>
                </Link>
              );
            })}
          </svg>
        </div>
      )}
    </section>
  );
}
