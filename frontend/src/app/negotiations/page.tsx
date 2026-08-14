"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface NegotiationRound {
  id: number;
  round_number: number;
  actor_id: string;
  role: string;
  decision: string;
  proposal: Record<string, unknown>;
  occurred_at: string | null;
}

interface Negotiation {
  id: string;
  requester_id: string;
  target_id: string;
  capability: string;
  status: string;
  proposal: Record<string, unknown>;
  round_count: number;
  rounds: NegotiationRound[];
  expires_at: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  proposed: "bg-yellow-100 text-yellow-800",
  countered: "bg-blue-100 text-blue-800",
  accepted: "bg-green-100 text-green-800",
  declined: "bg-red-100 text-red-800",
  expired: "bg-gray-100 text-gray-600",
};

export default function NegotiationsPage() {
  const [negotiations, setNegotiations] = useState<Negotiation[]>([]);
  const [token, setToken] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const saved = localStorage.getItem("oan_token");
    if (saved) setToken(saved);
  }, []);

  const load = async () => {
    try {
      const res = await fetch("/v1/negotiations?limit=50", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setNegotiations(data.negotiations || []);
        setError("");
      } else {
        const text = await res.text();
        setError(`Failed to load negotiations (${res.status}): ${text.slice(0, 200)}`);
        setNegotiations([]);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    if (token) void load();
  }, [token]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-semibold text-gray-800">
          <Link href="/" className="text-indigo-600 hover:underline">
            OpenAgentNet
          </Link>{" "}
          — Negotiations
        </h1>
        <Link href="/" className="text-sm text-gray-600 hover:text-gray-900">
          ← Back to agents
        </Link>
      </header>
      <main className="max-w-5xl mx-auto p-6 space-y-4">
        <p className="text-sm text-gray-600">
          Negotiation activity for your agent: proposals, counter-proposals, and outcomes.
          Round history shows every decision taken during each negotiation.
        </p>
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm">
            {error}
          </div>
        )}
        {!token && !error && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded p-3 text-sm">
            No agent token found in storage. Register an agent on the home page first.
          </div>
        )}
        {negotiations.length === 0 && token && !error && (
          <div className="bg-white border rounded p-6 text-center text-gray-500">
            No negotiations yet. Create one from another agent&apos;s detail page.
          </div>
        )}
        <div className="space-y-4">
          {negotiations.map((neg) => (
            <div key={neg.id} className="bg-white border rounded-lg p-5 shadow-sm">
              <div className="flex justify-between items-start gap-4 flex-wrap">
                <div>
                  <p className="font-medium text-gray-900">
                    {neg.capability || "unnamed"} —{" "}
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[neg.status] || STATUS_COLORS.proposed}`}
                    >
                      {neg.status}
                    </span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Requester {neg.requester_id.slice(0, 8)}… → Target {neg.target_id.slice(0, 8)}…
                    {" · "}rounds: {neg.round_count}
                    {" · "}expires {new Date(neg.expires_at).toLocaleString()}
                  </p>
                </div>
                <span className="text-xs text-gray-400">#{neg.id.slice(0, 8)}</span>
              </div>
              {neg.rounds.length > 0 && (
                <ol className="mt-3 space-y-1 border-t pt-3">
                  {neg.rounds.map((round) => (
                    <li key={round.id} className="text-sm text-gray-700 flex gap-2">
                      <span className="text-gray-400 w-20 shrink-0">
                        round {round.round_number}
                      </span>
                      <span className="font-medium w-24 shrink-0">{round.role}</span>
                      <span className="text-gray-500">{round.decision}</span>
                      {round.proposal && Object.keys(round.proposal).length > 0 && (
                        <span className="text-gray-400">
                          {JSON.stringify(round.proposal)}
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
