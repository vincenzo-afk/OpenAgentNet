# OpenAgentNet — State for Phase-2..7 completion plan (user follow-up request)

User request: "continue and fix the entire project which all the features left off fix all them" — i.e. complete the remaining roadmap phases (Phase 2 Trust & Reputation, Phase 3 Negotiation, Phase 4 Orchestration, Phase 5 Shared Memory, Phase 6 Marketplace depth; Phase 7 distributed execution/federation is out-of-scope/too large — propose as future).

## Completed earlier (pushed to main, commits 22f3b6d + 7369f79, authored vincenzo-afk)
Phase 1 done: registry, discovery, messaging w/ NATS JetStream + HTTP fallback, tasks, trust baseline, negotiations (basic), workflows (basic), memory (basic), marketplace (basic), heartbeat, e2e_test.py ALL PASSING, 24 pytest pass, schema audit ALL MATCH, frontend Next.js dashboard (agents, detail, marketplace, messages pages), CI workflow, CONTRIBUTING, LICENSE, README, roadmap Phase 1 marked complete.

## Environment (working in sandbox)
- Repo: /home/ubuntu/OpenAgentNet (git@main, origin vincenzo-afk/OpenAgentNet)
- Backend runs: uvicorn app.main:app on :8000, log /tmp/backend.log, cd backend, PYTHONPATH=/home/ubuntu/OpenAgentNet/backend
- DB: postgresql://openagentnet:openagentnet@localhost:5432/openagentnet (sudo -u postgres psql)
- Redis :6379, NATS jetstream store /tmp/natsdata on :4222
- JWT keys: backend/keys/jwt_private.pem (RSA, openssl genrsa 2048); generate via backend/scripts/generate-keys.sh
- E2E script: /home/ubuntu/OpenAgentNet/e2e_test.py (ALL CHECKS PASSED)
- Demo seed: backend/scripts/seed_demo.py + check_discover.py (token saved /tmp/demo_token.txt)
- Schema auditor: scripts/audit_schema.py
- Git push creds: user.name=vincenzo-afk user.email=itsmebk2007@gmail.com
- Kill server: pkill -f "uvicorn app.main"

## Remaining roadmap items (from docs/ROADMAP.md, all unchecked)
Phase 2 Trust & Reputation (v0.2.0):
- [ ] Endorsement system with weight by endorser trust (endorse exists — add weighting)
- [ ] Dispute submission and review queue (flag exists — add queue/review)
- [ ] Trust score components: endorsement_score, age_factor, dispute_penalty (model has columns, scoring partially implemented — verify wiring + make effective)
- [ ] Anomaly detection for reputation manipulation
- [ ] Trust history timeline per agent
- [ ] Dashboard: Trust score breakdown and history charts
- [ ] min_trust_score filter live in discovery (route accepts param; verify applied)

Phase 3 Negotiation (v0.3.0):
- [ ] Negotiation protocol implementation (create_proposal/respond/get exist)
- [ ] Proposal/counter/accept/decline state machine (verify states enforced)
- [ ] Session tokens for accepted negotiations (exists)
- [ ] Negotiation records attached to task records (attach negotiation_id to task)
- [ ] Dashboard: Negotiation activity view

Phase 4 Orchestration (v0.4.0):
- [ ] Workflow schema and DAG validation (add validation)
- [ ] Orchestration engine (dispatch, dependency tracking, retry) (currently pending forever — BUILD THIS)
- [ ] Workflow status events via NATS (publish events)
- [ ] Workflow failure handling and partial results
- [ ] Dashboard: Workflow graph visualizer (React Flow or simpler SVG)
- [ ] Example: 3-agent pipeline workflow

Phase 5 Shared Memory (v0.5.0):
- [ ] Memory object storage (exists: ephemeral+persistent)
- [ ] ACL enforcement on all memory reads (verify grant-based reads enforced)
- [ ] Streaming memory updates via NATS (publish memory events)
- [ ] Memory namespace isolation (verify namespaced)
- [ ] Dashboard: Memory browser for operators

Phase 6 Marketplace (v0.6.0):
- [ ] Marketplace listing schema pricing/SLA/tiers (exists partially)
- [ ] Search and browse marketplace (exists)
- [ ] Access tier management (free/paid/invite-only enforcement)
- [ ] Usage metering and billing hooks (webhook callout on task completion)
- [ ] Dashboard: Marketplace browse and listing management

Phase 7 (out of plan scope, propose future): federation, multi-region NATS, cross-region discovery, agent migration, K8s manifests.

## Existing service methods (known)
- trust/service.py: get_trust_record, record_outcome(db, task_id, success, execution_ms), endorse, flag, get_events
- negotiation/service.py: create_proposal, respond, get_negotiation (statuses proposed/accepted etc., session_token)
- orchestration/service.py: create_workflow, get_workflow, list_workflows (NO dispatch engine — tasks never progress)
- memory/service.py: write_memory, read_memory, list_memory, delete_memory (grants ACL in write; verify read enforcement)
- marketplace/service.py: create_listing, get_listing, search_listings, update_listing, delete_listing
- messaging/service.py: send_heartbeat, mark_inactive_agents, send_message, get_message, list_messages (+ report_task_result in api)
- discovery/service.py: search (with min_trust_score?), get_similar
- registry/service.py: register, get_agent, get_agent_by_did, update_agent, deregister_agent, list_agents, verify_agent_signature, rotate_key, authenticate_api_key

## New core files already built (earlier)
backend/app/core/identifiers.py (parse_agent_id), nats_client.py (connect/publish_to_agent/publish_event/publish_agent_announce/subscribe_agent_inbox), workers.py (task_delivery_worker, ttl_expiry_worker, heartbeat_worker, nats_inbox_listener), schemas in app/schemas/{agent,task,memory,marketplace,trust,negotiation,workflow}.py; models in app/models/*.py; migrations 001-004.

## Execution plan for plan mode
A. Phase 2: wire endorsement weighting into compute, implement dispute queue + review endpoints, verify min_trust_score in discovery, add trust timeline endpoint + anomaly detection worker, add dashboard trust charts.
B. Phase 3: enforce negotiation state machine, attach negotiation_id to tasks, dashboard negotiation view.
C. Phase 4: DAG validation, dispatch engine w/ dependency tracking + retry + NATS status events + failure/partial results; workflow page; 3-agent pipeline example.
D. Phase 5: enforce memory ACL on reads, NATS memory events, namespace isolation check, dashboard memory browser.
E. Phase 6: access tiers enforcement, usage metering + billing webhooks, listing management page in dashboard.
F. Tests: extend e2e_test.py to cover all new features; pytest new unit tests; schema audit; frontend build.
G. Docs: update ROADMAP (phases 2-6 complete), README; commit+push.

## THIS RUN progress (Phases 2-6)
Plan: /home/ubuntu/plan.md (approved). Working top-down: P2 -> P3 -> P4 -> P5 -> P6 -> tests/docs/push.
- P2 done in code: models/trust.py + reviewed_at/verified; migration 005 applied; services/trust/service.py rewritten (age sqrt growth, weighted endorsement 0.3 floor, ring-aware score, burst+ring anomalies, anomalies via audit+NATS, flag no-penalty-until-reviewed, list_disputes/mark_under_review/resolve_dispute +0.15 penalty); schemas added DisputeListResponse/DisputeResolveRequest/full DisputeResponse; api/v1/trust.py added GET /trust/disputes (admin), POST mark-review (admin), POST resolve (X-Operator-Secret vs env OPERATOR_SECRET); scripts/check_phase2.py written.
- NEXT: run check_phase2.py (export OPERATOR_SECRET=ops-secret), fix failures. Then P3.

## P2 check run diagnostics (round 1)
- parse_agent_id now handles uuid.UUID instances (added isinstance guard). Fixes 'ValueError: Invalid agent_id' that occurred when get_trust_record was called with a stored asyncpg UUID.
- IMPORTANT quirk: /v1/trust/{agent_id} is the LAST route checked by GET (path /trust/{agent_id} also matches /trust/endorse-like paths? No — actual issue: check script calls /trust/disputes correctly). The 500 chain came from get_trust_record receiving UUID objects from ORM rows (fixed).
- seed_demo re-registration creates NEW agent UUIDs per run (deterministic per key pair but script regenerates keys?) — token's agent_id may differ from latest discover ids. Seed uses fresh keys each run => different IDs each run. OK as long as checks read IDs from discover, not from token.
- check_phase2.py now works for resolve/penalty/timeline; failures left: endorse 500 (get_trust_record ValueError — same UUID fix applies, rerun needed).

## P2 round 2 (current debugging)
- Fixes applied: parse_agent_id handles uuid.UUID; burst scalar() called once; scalar() bug gone; endorse/dup/mutual/all pass now.
- REMAINING P2 BUG: GET /v1/trust/disputes 500s -> routed to get_trust_score(agent_id='disputes') even though GET /disputes route exists. __pycache__ cleared, server killed+restarted PID 10190 — STILL routes to get_trust_score. openapi.json shows '/v1/trust/{agent_id}' registered BEFORE '/v1/trust/disputes' (trust router is included in main.py before common? no — trust_router order fine; the router order within trust.py: /{agent_id} is FIRST in file; Starlette exact-match should still win...
- HYPOTHESIS: FastAPI router order in openapi matches registration order, and Starlette matches registration order; literal routes DON'T automatically win over path params in older behavior — route defined earlier ({agent_id}) matches first. FIX: move the /{agent_id} + /{agent_id}/events routes to the END of trust.py (literal routes first).
- Also check other routers for same pattern: e.g. /v1/agents/{agent_id} routes vs literal sub-routes. marketplace/trust only.
- OPERATOR_SECRET=ops-secret needed for resolve. Server: nohup env OPERATOR_SECRET=ops-secret uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 & (from backend dir). Kill: kill <pid>. Redis rate limit: redis-cli FLUSHDB between runs if 429.
- seed_demo: PYTHONPATH=. python3 scripts/seed_demo.py (in backend dir); saves token to /tmp/demo_token.txt; re-registers fresh key pairs each run => different agent IDs each run; demo traffic also seeds listing/endorse via old token idempotent-ish.
- check_phase2.py: cd backend && OPERATOR_SECRET=ops-secret python3 scripts/check_phase2.py (full pipeline, re-seeds first).
- P2 check expected outputs (from last run): trust record 200; endorse 201; dup 400; dispute 201; list must be 200; mark-review 200 under_review; resolve no-secret 401; resolve 200 resolved_valid; penalty +0.15; events 200 incl dispute_filed+dispute_resolved; mutual endorse 201 + anomaly events.

## PHASE 2 — COMPLETE & PUSHED
- Fixed: trust.py route order (literal /disputes routes BEFORE /{agent_id} catch-all); trust service lazy TrustRecord on endorsement receipt; get_events anomaly support without record; JWT key paths absolute via Path(__file__) chains (fixes pytest 24 pass from repo root).
- check_phase2.py ALL PASSING; e2e green; pushed to GitHub.

## PHASE 3 — SERVICE CODE DONE, check_phase3.py ALL PASSING (not yet committed)
- app/models/negotiation_round.py (NegotiationRound: negotiation_id, round_number, actor_id, role requester|target, decision proposed|accepted|countered|declined, proposal JSONB, occurred_at). Check constraints at table level. Migration 006_negotiation_history.py (down_revision=005), APPLIED. models/__init__.py exports it.
- app/services/negotiation/service.py rewritten: VALID_TRANSITIONS state machine (proposed/countered -> countered|accepted|declined|expired; terminal empty); MAX_ROUNDS=3 via negotiation.round_count; _expire_due auto-expiry on respond; participants-only respond check (requester OR target); NATS events via nats_client.publish_event('negotiation', {type: negotiation_created/negotiation_countered/negotiation_acceptedd/negotiation_declinedd, negotiation_id, ...}); session_token issued on accept; response stores full counter_proposal/agreed_constraints; get_negotiation returns rounds history; list_negotiations(agent, status, limit, offset) w/ total.
- app/api/v1/negotiations.py: GET '' list (before /{id} catch-all), respond passes actor_id from JWT.
- schemas/negotiation.py: added round_number to NegotiationResponseSchema, NegotiationRoundDetail, NegotiationListResponse.
- scripts/check_phase3.py ALL PASSING (creates 2 fresh agents itself — do NOT reuse demo_token, which belongs to stale agent 6a040e9b).
- e2e_test.py updated negotiation section: e2e agent proposes to latest demo-summarizer using demo_token for target auth; counter->decline-wrong-side(400)->accept->get detail+rounds->list. demo_token loaded from /tmp/demo_token.txt (fallback '') at module top.
- NATS: OAN_EVENTS stream shows 32 msgs incl negotiation_* events (fetch on JetStreamContext works; my earlier 'no attribute fetch' error was a usage bug).
- TODO: commit+push Phase 3; then Phase 4.

## ENV REMINDERS (all phases)
- Server: cd /home/ubuntu/OpenAgentNet/backend && nohup env OPERATOR_SECRET=ops-secret uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 & ; kill $(pgrep -f "uvicorn app.main:app --port 8000")
- Migrations: cd backend && DATABASE_URL=postgresql://openagentnet:openagentnet@localhost:5432/openagentnet alembic upgrade head
- pytest 24 tests; e2e: python3 e2e_test.py; redis-cli FLUSHDB between runs; PYTHONPATH=. for scripts.
- Git: git -c user.name="vincenzo-afk" -c user.email="itsmebk2007@gmail.com" commit/push origin main.
- Demo agents go 'inactive' (heartbeat worker); discover only returns active agents.
- parse_agent_id handles uuid.UUID + str + did:oan: prefix.
- Route order: literal routes BEFORE /{param} catch-alls (e2e fixed in trust.py; negotiations.py already ordered correctly).
