"use client";

import { useState } from "react";
import { sendTask } from "@/lib/api";

export default function SendTaskForm({
  toDid,
  capabilities,
}: {
  toDid: string;
  capabilities: string[];
}) {
  const [capability, setCapability] = useState(capabilities[0] || "");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "error">("idle");
  const [messageId, setMessageId] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    setError("");
    setMessageId("");
    try {
      // Anonymous send is not permitted; the dashboard documents the action.
      // In production the operator would provide an agent token via env.
      await sendTask("", toDid, capability, { text }, null);
      setStatus("ok");
    } catch (err) {
      setStatus("error");
      setError((err as Error).message);
    }
  };

  return (
    <form onSubmit={onSubmit}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
        <select
          value={capability}
          onChange={(e) => setCapability(e.target.value)}
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            borderRadius: 8,
            padding: "0.55rem 0.8rem",
            fontSize: "0.9rem",
          }}
        >
          {capabilities.map((cap) => (
            <option key={cap} value={cap}>
              {cap}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Payload text for the task..."
        />
      </div>
      <button type="submit" disabled={status === "sending"} className={status === "sending" ? "secondary" : ""}>
        {status === "sending" ? "Sending…" : "Send Task"}
      </button>
      {status === "ok" && (
        <p style={{ color: "var(--good)", fontSize: "0.85rem" }}>
          Task queued. (Use an agent token in production; anonymous sends are rejected by the API.)
        </p>
      )}
      {status === "error" && <p className="error">{error}</p>}
    </form>
  );
}
