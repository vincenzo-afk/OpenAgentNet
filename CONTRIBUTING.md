# Contributing to OpenAgentNet

Thank you for your interest in OpenAgentNet! This document covers how to set up
a development environment, run the tests, and get your changes merged.

## Development environment

OpenAgentNet requires three infrastructure services plus the application:

| Service | Version | Purpose |
|---|---|---|
| PostgreSQL | 15+ | Persistent store for agents, tasks, trust records |
| Redis | 7+ | Rate limiting, revocation lists, caches |
| NATS Server | 2.10+ | Agent messaging with JetStream |
| Python | 3.11+ | Backend runtime (FastAPI) |
| Node.js | 20+ | Dashboard frontend (Next.js) |

The fastest way to bring everything up is Docker Compose:

```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d
```

Then bootstrap the backend:

```bash
cp .env.example .env
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash scripts/generate-keys.sh
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Verify the stack with the end-to-end smoke test:

```bash
cd ..
python e2e_test.py   # expects ALL CHECKS PASSED
```

## Running tests

```bash
# Unit + integration tests (backend)
cd backend && pytest tests/

# Full end-to-end flow against a running server
cd .. && python e2e_test.py

# Frontend build check
cd frontend && pnpm build
```

CI (`.github/workflows/ci.yml`) runs all three on every push and pull request.
Please make sure all three pass before opening a pull request.

## Adding schema changes

Create a new Alembic migration:

```bash
cd backend
alembic revision -m "describe the change" --autogenerate
```

Edit the generated file, verify `alembic upgrade head` works against a fresh
database, and keep `scripts/audit_schema.py` green:

```bash
PYTHONPATH=. python ../scripts/audit_schema.py   # expects ALL MATCH
```

## Code conventions

- Follow the existing module layout: `app/api/v1/` (routes),
  `app/services/` (business logic), `app/models/` (SQLAlchemy),
  `app/schemas/` (Pydantic), `app/core/` (infra glue).
- Resolve external agent identifiers with `app/core/identifiers.parse_agent_id`
  rather than raw `uuid.UUID(...)` casts — agents may present a UUID, a base58
  key fingerprint, or a `did:oan:` identifier.
- Message envelopes are deduplicated by SHA-256 of the canonical JSON; do not
  re-implement hashing elsewhere.
- Type-annotate new code and keep Pydantic v2 schemas (use `ConfigDict`, not
  the deprecated `class Config`).

## Pull requests

- One logical change per PR.
- Reference the feature/roadmap item it addresses (see `docs/ROADMAP.md`).
- Include test coverage: unit tests for services, and update `e2e_test.py`
  when adding endpoints.
- Update documentation when behaviour changes.

## Reporting security issues

Please email itsmebk2007@gmail.com rather than opening a public issue.
See `docs/SECURITY.md` for the security model.
