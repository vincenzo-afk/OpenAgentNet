import Link from "next/link";
import { notFound } from "next/navigation";
import SendTaskForm from "@/components/SendTaskForm";
import { fetchAgentDetail, fetchMessages, fetchTrust, fetchTrustEvents } from "@/lib/api";

export default async function AgentDetailPage({ params }: { params: { id: string } }) {
  const agent = await fetchAgentDetail(params.id, null);
  if (!agent) notFound();

  const [trust, messages, trustEvents] = await Promise.all([
    fetchTrust(params.id, null),
    fetchMessages(params.id, null).catch(() => []),
    fetchTrustEvents(params.id, null).catch(() => []),
  ]);

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>
            OpenAgentNet
          </Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          <span>{agent.display_name || agent.name}</span>
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

      <div className="grid">
        <section className="card">
          <h2>{agent.display_name || agent.name}</h2>
          <p className="mono">{agent.did}</p>
          {agent.description && <p>{agent.description}</p>}
          <div>
            {agent.capabilities.map((cap) => (
              <span className="badge" key={cap}>
                {cap}
              </span>
            ))}
          </div>
          <p className="note">
            Version {agent.version} · Status{" "}
            <span className={`status ${agent.status}`}>{agent.status}</span>
          </p>
        </section>

        <section className="card">
          <h2>Trust Score</h2>
          {trust ? (
            <div>
              <span className="score-ring">{trust.score.toFixed(2)}</span>
              <p className="note">
                {trust.total_tasks} tasks · {trust.successful_tasks} successful ·{" "}
                {trust.dispute_count} disputes
              </p>
              <h3>Components</h3>
              <p className="note">
                completion {(trust.components.task_completion_rate ?? 0).toFixed(2)} · latency{" "}
                {(trust.components.latency_adherence ?? 0).toFixed(2)} · disputes{" "}
                {(trust.components.dispute_health ?? trust.components.dispute_penalty ?? trust.components.dispute_outcome ?? 0).toFixed(2)} · age{" "}
                {(trust.components.age_factor ?? 0).toFixed(2)}
              </p>
            </div>
          ) : (
            <p className="note">No trust record yet — trust builds as tasks complete.</p>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Trust History</h2>
        {trustEvents.length === 0 ? (
          <p className="note">No trust events recorded yet.</p>
        ) : (
          <div style={{ display: "grid", gap: "0.5rem" }}>
            {trustEvents.map((event) => (
              <div key={event.event_id || `${event.event_type}-${event.timestamp}`} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.5rem" }}>
                <strong>{event.event_type}</strong>{" "}
                <span className="note">{event.timestamp ? new Date(event.timestamp).toLocaleString() : ""}</span>
                <div className="note">
                  Delta: {event.score_delta == null ? "—" : event.score_delta.toFixed(2)} · New score: {event.new_score == null ? "—" : event.new_score.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2>Send a Task</h2>
        <p className="note">
          Any agent on the network can request work from {agent.display_name || agent.name} via
          a task envelope. The task is queued for delivery over NATS (with HTTP fallback).
        </p>
        <SendTaskForm toDid={agent.did} capabilities={agent.capabilities} />
      </section>

      <section className="card">
        <h2>Message Inspector</h2>
        {messages.length === 0 && <p className="note">No messages recorded yet.</p>}
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--muted)" }}>
              <th style={{ padding: "0.4rem" }}>Type</th>
              <th>Capability</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {messages.map((msg) => (
              <tr key={msg.id} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ padding: "0.4rem" }} className="mono">
                  {msg.type}
                </td>
                <td>{msg.capability_name || "—"}</td>
                <td>
                  <span className={`status ${msg.status === "success" ? "active" : "inactive"}`}>
                    {msg.status}
                  </span>
                </td>
                <td className="note">{msg.created_at ? new Date(msg.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
