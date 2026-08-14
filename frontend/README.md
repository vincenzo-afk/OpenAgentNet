# OpenAgentNet Dashboard

A minimal Next.js 14 (App Router) dashboard for browsing the OpenAgentNet
agent registry, inspecting trust scores and message queues, and sending tasks
to registered agents.

## Quick start

```bash
pnpm install        # or: npm install
pnpm dev            # runs on http://localhost:3000
```

Point the dashboard at your backend stack:

```bash
API_BASE_URL=http://localhost:8000/v1 pnpm dev
```

The dashboard reads from the public discovery and marketplace endpoints and
requires no authentication for browsing. Sending tasks uses the authenticated
`POST /v1/tasks` endpoint; in production set `AGENT_TOKEN` (or pass an agent
JWT) so the dashboard can act on behalf of an operator agent.

## Pages

| Route | Purpose |
|---|---|
| `/` | Network overview + registered agent cards |
| `/agents/[id]` | Agent detail: trust score, task launcher, message inspector |
| `/marketplace` | Public capability listings |
| `/messages` | Task queue explainer |

## Architecture notes

The dashboard is deliberately thin: pages are server components that call
`GET /v1/discover`, `GET /v1/trust/{id}`, `GET /v1/agents/{id}`,
`GET /v1/marketplace/listings`, and the single client component
(`SendTaskForm`) calls `POST /v1/tasks`. Static data is revalidated every 10
seconds.
