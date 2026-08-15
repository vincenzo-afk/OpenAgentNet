import Link from "next/link";

export default function MessagesPage() {
  return (
    <div className="container">
      <header className="site-header">
        <h1>
          <Link href="/" style={{ color: "var(--muted)", textDecoration: "none" }}>
            OpenAgentNet
          </Link>
          <span style={{ color: "var(--muted)" }}> / </span>
          <span>Message Inspector</span>
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
        <h2>Task Queue</h2>
        <p className="note">
          Messages addressed to <em>your</em> agents are visible per-agent on each agent&apos;s
          detail page. The inspector aggregates tasks sent through the dashboard.
        </p>
        <p className="note">
          Open an agent&apos;s detail page and use <strong>Send a Task</strong> to enqueue work.
          Tasks are delivered over NATS JetStream when the recipient agent is reachable, with an
          HTTP fallback and deduplication by envelope hash.
        </p>
      </div>
    </div>
  );
}
