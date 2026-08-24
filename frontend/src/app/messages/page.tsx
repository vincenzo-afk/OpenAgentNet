"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { fetchMessages, Message } from "@/lib/api";

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oan_token");
}

function statusColor(status: string): string {
  if (["success", "acked", "running"].includes(status)) return "#2d6a4f";
  if (["failed", "timeout", "cancelled"].includes(status)) return "#9b1c1c";
  return "#6b7280";
}

export default function MessagesPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      const currentToken = token();
      if (!currentToken) {
        if (!cancelled) {
          setAuthenticated(false);
          setLoading(false);
        }
        return;
      }
      try {
        const items = await fetchMessages("", currentToken);
        if (!cancelled) {
          setMessages(items);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Unable to load message history.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const visibleMessages = useMemo(
    () => (status === "all" ? messages : messages.filter((message) => message.status === status)),
    [messages, status],
  );

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>
            OpenAgentNet
          </Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          Message Inspector
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
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <h2>Recent task messages</h2>
            <p className="note">Messages for the authenticated agent, refreshed every 10 seconds.</p>
          </div>
          <label>
            Status{" "}
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="timeout">Timeout</option>
            </select>
          </label>
        </div>

        {!authenticated && (
          <p className="note" style={{ color: "var(--danger, #9b1c1c)" }}>
            No agent token found in localStorage. Set <code>localStorage.setItem(&quot;oan_token&quot;, token)</code> to inspect messages.
          </p>
        )}
        {error && <p className="note" style={{ color: "var(--danger, #9b1c1c)" }}>{error}</p>}
        {loading && <p className="note">Loading messages…</p>}
        {!loading && authenticated && visibleMessages.length === 0 && <p className="note">No messages match this filter.</p>}
        {visibleMessages.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "0.5rem" }}>Direction</th>
                  <th>Type</th>
                  <th>Capability</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {visibleMessages.map((message) => (
                  <tr key={message.id || message.message_id} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "0.5rem" }} className="mono">
                      {message.from_agent_id} → {message.to_agent_id}
                    </td>
                    <td className="mono">{message.type}</td>
                    <td>{message.capability_name || message.capability || "—"}</td>
                    <td>
                      <span className="status" style={{ color: statusColor(message.status) }}>
                        {message.status}
                      </span>
                    </td>
                    <td className="note">{message.created_at ? new Date(message.created_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
