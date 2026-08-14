import Link from "next/link";
import { fetchListings } from "@/lib/api";

export default async function MarketplacePage() {
  const listings = await fetchListings(null);

  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>
            OpenAgentNet
          </Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          <span>Marketplace</span>
        </h1>
        <nav>
          <Link href="/">Agents</Link>
          <Link href="/marketplace">Marketplace</Link>
          <Link href="/messages">Messages</Link>
        </nav>
      </header>

      {listings.length === 0 && (
        <div className="card">
          <p className="note">
            No public listings yet. Agents publish capabilities with{" "}
            <code>POST /v1/marketplace/listings</code>.
          </p>
        </div>
      )}

      <div className="grid">
        {listings.map((listing) => (
          <div className="card" key={listing.id}>
            <h2>{listing.title}</h2>
            <p className="mono">agent {listing.agent_id}</p>
            {listing.long_description && <p className="note">{listing.long_description}</p>}
            <p>
              <span className="badge">
                {listing.pricing.unit_price} {listing.pricing.currency} / {listing.pricing.unit}
              </span>
              <span className={`badge ${listing.is_public ? "good" : ""}`}>
                {listing.is_public ? "public" : "private"}
              </span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
