"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://localhost:8000/v1";

interface WorkflowStep {
  id: string;
  agent_capability: string;
  depends_on: string[];
  constraints?: Record<string, unknown>;
  payload?: Record<string, unknown> | null;
}

interface WorkflowDefinition {
  tasks: WorkflowStep[];
}

interface FailedStep {
  step_id?: string;
  error: string;
}

interface Workflow {
  workflow_id: string;
  name: string | null;
  status: string;
  owner_agent_id?: string;
  definition?: WorkflowDefinition;
  context?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: { failed_steps?: FailedStep[] } | null;
  created_at?: string;
  updated_at?: string;
}

type StatusKind =
  | "success"
  | "partial"
  | "running"
  | "pending"
  | "failed"
  | "cancelled";

const STATUS_BADGE: Record<StatusKind, string> = {
  success: "#2d6a4f",
  partial: "#7a6c1f",
  running: "#1f5fa3",
  pending: "#6b7280",
  failed: "#9b1c1c",
  cancelled: "#6b7280",
};

function statusStyle(status: string): React.CSSProperties {
  const color = STATUS_BADGE[status as StatusKind] ?? "#6b7280";
  return {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: 999,
    fontSize: "0.8em",
    fontWeight: 600,
    color: "#ffffff",
    backgroundColor: color,
    textTransform: "capitalize",
  };
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oan_token");
}

async function listWorkflows(): Promise<Workflow[]> {
  const res = await fetch(`${BASE_URL}/workflows?limit=50`, {
    headers: { Authorization: `Bearer ${token() ?? ""}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  const items: Workflow[] = Array.isArray(data.items) ? data.items : data.agents ?? [];
  return items.sort(
    (a, b) =>
      new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime(),
  );
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      if (!token()) return;
      try {
        const items = await listWorkflows();
        if (cancelled) return;
        setWorkflows(items);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const missingAuth = useMemo(() => typeof window !== "undefined" && !token(), []);

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>
            OpenAgentNet
          </Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          <span>Workflow Inspector</span>
        </h1>
        <nav>
          <Link href="/">Agents</Link>
          <Link href="/marketplace">Marketplace</Link>
          <Link href="/negotiations">Negotiations</Link>
          <Link href="/memory">Memory</Link>
          <Link href="/messages">Messages</Link>
          <Link href="/workflows">Workflows</Link>
        </nav>
      </header>

      <div className="card">
        <h2>Workflow Runs</h2>
        <p className="note">
          Multi-step jobs dispatched by agents. Each workflow is a directed acyclic graph of
          steps that the orchestration engine executes topologically, resolving agents by
          capability and retrying transient failures. Step results are reported back over NATS
          JetStream with an HTTP fallback.
        </p>
        {missingAuth && (
          <p className="note" style={{ color: "var(--danger, #9b1c1c)" }}>
            No agent token found in localStorage. Set{" "}
            <code>localStorage.setItem(&quot;oan_token&quot;, token)</code> or register an
            agent to authenticate.
          </p>
        )}
        {error && <p className="note" style={{ color: "var(--danger, #9b1c1c)" }}>{error}</p>}
        {workflows.length === 0 && !error && (
          <p className="note">
            No workflow runs yet. Use <strong>Check Phase 4</strong> (or the dispatch API) to
            create and run a multi-step pipeline.
          </p>
        )}

        {workflows.map((wf) => {
          const steps = wf.definition?.tasks ?? [];
          const failed = wf.error?.failed_steps ?? [];
          return (
            <div
              key={wf.workflow_id}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: 8,
                padding: "12px 16px",
                marginBottom: 12,
                marginTop: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <strong>
                  {wf.name ?? wf.workflow_id.slice(0, 8)}{" "}
                  <span className="mono" style={{ fontWeight: 400, color: "var(--muted)" }}>
                    {wf.workflow_id.slice(0, 12)}
                  </span>
                </strong>
                <span style={statusStyle(wf.status)}>{wf.status}</span>
              </div>

              {steps.length > 0 && (
                <div className="mono" style={{ fontSize: "0.85em", marginTop: 8 }}>
                  <div style={{ color: "var(--muted)", marginBottom: 4 }}>
                    steps: {steps.map((s) => s.id).join(" -> ")}
                  </div>
                  <table style={{ borderCollapse: "collapse", width: "100%" }}>
                    <tbody>
                      {steps.map((s) => (
                        <tr key={s.id}>
                          <td style={{ padding: "2px 10px 2px 0", minWidth: 110 }}>
                            {s.id}
                          </td>
                          <td style={{ padding: "2px 10px 2px 0" }}>
                            capability: {s.agent_capability}
                          </td>
                          <td style={{ color: "var(--muted)", padding: "2px 0" }}>
                            deps: {s.depends_on.length ? s.depends_on.join(", ") : "none"}
                          </td>
                          <td>
                            {failed.some(
                              (f) => f.step_id === s.id || (!f.step_id && f.error),
                            ) && (
                              <span
                                style={{
                                  color: "#9b1c1c",
                                  fontWeight: 600,
                                  fontSize: "0.9em",
                                }}
                              >
                                FAILED
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {failed.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    padding: "6px 10px",
                    borderRadius: 6,
                    backgroundColor: "#fdecec",
                    fontSize: "0.85em",
                  }}
                >
                  {failed.map((f, i) => (
                    <div key={i}>
                      {f.step_id ? `${f.step_id}: ` : ""}
                      <span className="mono">{f.error}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
