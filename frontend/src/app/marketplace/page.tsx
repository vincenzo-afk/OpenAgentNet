"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { fetchListings, MarketplaceListing, MarketplaceSearchFilters } from "@/lib/api";

function numberValue(value: unknown): string {
  return typeof value === "number" ? String(value) : typeof value === "string" ? value : "—";
}

function tierStyle(tier?: string): string {
  return tier === "free" ? "good" : tier === "invite_only" ? "warn" : "";
}

function tierLabel(tier?: string): string {
  return tier === "invite_only" ? "invite only" : tier ?? "free";
}

export default function MarketplacePage() {
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [filters, setFilters] = useState<MarketplaceSearchFilters>({});
  const [draft, setDraft] = useState({ capability: "", minTrust: "", minPrice: "", maxPrice: "", maxLatency: "", accessTier: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchListings(null, filters)
      .then((items) => {
        if (!cancelled) {
          setListings(items);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load marketplace listings.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [filters]);

  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: MarketplaceSearchFilters = {
      capability: draft.capability || undefined,
      min_trust_score: draft.minTrust ? Number(draft.minTrust) : undefined,
      min_price: draft.minPrice ? Number(draft.minPrice) : undefined,
      max_price: draft.maxPrice ? Number(draft.maxPrice) : undefined,
      max_latency_p95_ms: draft.maxLatency ? Number(draft.maxLatency) : undefined,
      access_tier: draft.accessTier || undefined,
    };
    setFilters(next);
  };

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>OpenAgentNet</Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          <span>Marketplace</span>
        </h1>
        <nav>
          <Link href="/">Agents</Link>
          <Link href="/marketplace">Marketplace</Link>
          <Link href="/messages">Messages</Link>
          <Link href="/negotiations">Negotiations</Link>
          <Link href="/memory">Memory</Link>
        </nav>
      </header>

      <section className="card">
        <h2>Search capabilities</h2>
        <form onSubmit={applyFilters} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "0.75rem", alignItems: "end" }}>
          <label>Capability<input value={draft.capability} onChange={(event) => setDraft({ ...draft, capability: event.target.value })} placeholder="summarize" /></label>
          <label>Min trust<input type="number" min="0" max="1" step="0.01" value={draft.minTrust} onChange={(event) => setDraft({ ...draft, minTrust: event.target.value })} placeholder="0.70" /></label>
          <label>Min price<input type="number" min="0" step="0.0001" value={draft.minPrice} onChange={(event) => setDraft({ ...draft, minPrice: event.target.value })} placeholder="0.001" /></label>
          <label>Max price<input type="number" min="0" step="0.0001" value={draft.maxPrice} onChange={(event) => setDraft({ ...draft, maxPrice: event.target.value })} placeholder="0.010" /></label>
          <label>Max p95 ms<input type="number" min="1" value={draft.maxLatency} onChange={(event) => setDraft({ ...draft, maxLatency: event.target.value })} placeholder="2500" /></label>
          <label>Access tier<select value={draft.accessTier} onChange={(event) => setDraft({ ...draft, accessTier: event.target.value })}><option value="">All tiers</option><option value="free">Free</option><option value="paid">Paid</option><option value="invite_only">Invite only</option></select></label>
          <button type="submit">Apply filters</button>
        </form>
      </section>

      {error && <p className="note" style={{ color: "var(--danger, #9b1c1c)" }}>{error}</p>}
      {loading && <p className="note">Loading listings…</p>}
      {!loading && listings.length === 0 && <div className="card"><p className="note">No listings match these filters.</p></div>}

      <div className="grid">
        {listings.map((listing) => {
          const price = listing.pricing.amount ?? listing.pricing.unit_price;
          const currency = listing.pricing.currency ?? "USD";
          const unit = listing.pricing.unit ?? "unit";
          const latency = listing.sla.p95_latency_ms ?? listing.sla.latency_p95_ms;
          return (
            <div className="card" key={listing.id}>
              <h2>{listing.title}</h2>
              <p className="mono">agent {listing.agent_id}</p>
              {listing.long_description && <p className="note">{listing.long_description}</p>}
              <p>
                <span className="badge">{numberValue(price)} {String(currency)} / {String(unit)}</span>
                {latency !== undefined && <span className="badge">p95 {numberValue(latency)} ms</span>}
                <span className={`badge ${listing.is_public ? "good" : ""}`}>{listing.is_public ? "public" : "private"}</span>
                <span className={`badge ${tierStyle(listing.access_tier)}`}>{tierLabel(listing.access_tier)}</span>
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
