# Engineering Plan

This document describes how OpenAgentNet will be built: team conventions, technical decisions, and the execution sequence.

---

## Execution Sequence

### Week 1–2: Foundation

1. Finalize all documentation (in progress).
2. Set up repository: branch protection, CI, linting.
3. Initialize PostgreSQL schema and Alembic migrations.
4. Implement agent registration endpoint with Ed25519 proof verification.
5. Implement JWT issuance and middleware.
6. Write unit tests for crypto operations.

### Week 3: Discovery

1. Implement Redis capability index.
2. Implement discovery search endpoint.
3. Wire registration to Redis index updates.
4. Write integration tests for discovery.

### Week 4–5: Messaging

1. Set up NATS JetStream with stream configuration.
2. Implement HTTP message delivery (POST to agent endpoint).
3. Implement NATS message delivery path.
4. Add message dedup and replay protection.
5. Implement signature verification on inbound messages.

### Week 6: Dashboard

1. Next.js project setup.
2. Agent list page.
3. Agent detail page with capability and trust info.
4. Message inspector.
5. Basic graph with React Flow.

### Week 7: Sample Agents

1. Build `echo` agent (returns input).
2. Build `summarizer` agent (uses BART or any summarizer).
3. Build `classifier` agent (simple text classifier).
4. Document how to run all three locally.

### Week 8: Hardening

1. End-to-end integration tests.
2. Load testing (target: 500 concurrent agents, 10k msgs/min).
3. Security review of auth flow.
4. Docs pass: ensure all public APIs are documented.
5. Phase 1 release cut.

---

## Development Conventions

### Git Workflow

- `main` — always deployable.
- `develop` — integration branch.
- Feature branches: `feature/{slug}` (e.g., `feature/registration-endpoint`).
- Bug fixes: `fix/{slug}`.
- No force-push to `main` or `develop`.
- PR requires 1 reviewer approval and passing CI.

### Commit Messages

Follow Conventional Commits:

```
feat(registry): add Ed25519 proof verification
fix(discovery): handle empty capability list in query
docs(api): add trust endpoint documentation
test(messaging): add NATS delivery integration test
chore(deps): upgrade fastapi to 0.111.0
```

### Code Style

- Python: `ruff` for linting, `black` for formatting, `mypy` for type checking.
- TypeScript: `eslint` + `prettier`.
- All CI checks must pass before merge.

### Testing Requirements

- Unit tests for all service functions.
- Integration tests for all API routes.
- Target 80% line coverage on `backend/app/services/`.
- E2E tests for the full registration → discovery → message flow.

### Environment Variables

Never commit secrets. Use `.env.example` as a template. In CI, use GitHub secrets.

---

## Key Technical Decisions Log

| Decision | Chosen | Alternatives Considered | Rationale |
|---|---|---|---|
| Messaging transport | NATS JetStream | WebSockets, RabbitMQ, Kafka | Low latency, at-least-once delivery, lightweight ops |
| Database | PostgreSQL | MongoDB, DynamoDB | ACID, strong typing, full SQL for complex trust queries |
| Auth crypto | Ed25519 | RSA, ECDSA | Fast verification, small signatures, modern standard |
| API framework | FastAPI | Django, Flask, Starlette | Native async, auto-generated docs, Pydantic integration |
| Initial topology | Modular monolith | Microservices from day 1 | Faster iteration; clean interfaces allow later extraction |
| Frontend | Next.js | SvelteKit, Remix | Widest ecosystem, strong TypeScript, familiar to contributors |

---

## CI/CD Pipeline

```yaml
# .github/workflows/ci.yml (summary)
on: [push, pull_request]

jobs:
  backend:
    - ruff check backend/
    - black --check backend/
    - mypy backend/app/
    - pytest tests/unit tests/integration --cov=backend/app/services

  frontend:
    - eslint frontend/
    - prettier --check frontend/
    - tsc --noEmit

  e2e:
    - docker compose up -d
    - pytest tests/e2e/
    - docker compose down
```
