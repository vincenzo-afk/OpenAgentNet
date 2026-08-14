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

## PHASE 3 — COMPLETE & PUSHED (commit 9c974e6, revert of pnpm-workspace in bb0e628)
- All done: state machine, counter rounds (MAX_ROUNDS=3), auto-expiry, NATS events, list endpoint, NegotiationsRound model + migration 006, e2e updated, frontend /negotiations page + nav link. e2e ALL PASSING, check_phase3.py ALL PASSING.

## PHASE 4 — IN PROGRESS
- orchestration/service.py rewritten: validate_dag (dup/dangling/cycle Kahn's), topological_order, create_workflow validates + spawns asyncio.create_task(_run_workflow) fire-and-forget; _run_workflow owns its own session via get_session_factory(); dispatch loop: dep check (_dep_successful allows success|partial), cascade-fail on dep failure, _execute_step resolves active agent via Agent.capabilities.contains([{"name": ...}]) JSONB, prefers non-owner host, sends via MessagingService.send_message(envelope, owner_id), polls Task until terminal (success/partial/failed/declined/timeout/cancelled), MAX_RETRIES=2, retries on Exception w/ 1s backoff, results stored on WorkflowTask, workflow aggregates to success/partial/failed with error dict; NATS events: workflow_created/started/step_completed/step_partial/step_failed/partial/failed/completed via nats_client.publish_event('workflow', {...}).
- Task statuses: pending, acked, running, success, partial, failed, declined, cancelled, timeout. TTL expiry worker sets 'timeout'.
- In sandbox no real agent endpoint exists, so dispatched tasks will HTTP-fail/time out → e2e workflow expect 201 create; GET may show failed/partial — e2e only checks create 201, get 200, list 200 → OK as long as engine doesn't break. WorkflowTask has NO updated_at column (avoid referencing).
- Workflow models: Workflow (id, owner_agent_id, name, status pending|running|success|partial|failed|cancelled, definition JSONB, context, result, error, created_at, updated_at, completed_at), WorkflowTask (id, workflow_id, task_id UUID|null, node_id, capability_name, depends_on JSONB, status, result, created_at).
- Routes: POST/GET/GET workflows (prefix /workflows, scope delegate:workflow), literal GET '' before /{workflow_id} catch-all.
- TODO P4: migration if needed (none yet — model unchanged), check e2e with engine (may need MAX_STEP_RUN_TIME_SECONDS lower for tests — but 120s poll ok; step timeouts will mark workflow failed), check_phase4.py, frontend workflow graph page (routes /workflows page exists? frontend has workflows route? verify), worker task execution simulation: for real step success in check_phase4, seed an agent with summarization capability whose endpoint is a local test server? SIMPLER: register a fake HTTP agent (http.server on :9090 responding 200) whose endpoint receives task POSTs and auto-reports result via POST /v1/messages/{task_id}/result — the check script can stand up such an endpoint thread. That gives a genuinely working pipeline demo.
- e2e negotiation uses registered e2e-target-summarizer (fresh key pair) with target_auth. e2e ALL PASSING.
- pytest 24 pass; check_phase2/phase3 ALL PASSING.

## Key env (repeated)
- Server PID via pgrep -f "uvicorn app.main:app --port 8000"; start: cd backend && nohup env OPERATOR_SECRET=ops-secret uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 &
- redis-cli FLUSHDB between runs; alembic upgrade head; git push with vincenzo-afk/itsmebk2007@gmail.com.
- Workflow engine polls via TaskModel patched after import at module end.

## P4 debugging state (2026-08-14)
- check_phase4.py written: fake HTTP agent server on :9444 auto-reports task results via /v1/messages/{id}/result w/ FAKE_AGENT_TOKEN; owner agent w/ delegate:workflow cap. Manifest fields must include: protocol_version 0.1.0, display_name None, owner{id,type,name}, health_endpoint None, permissions_required [], permissions_offered [], tags, metadata {} — matches e2e_test pattern.
- DAG validation + workflow create both PASS now. get_workflow + list_workflows restored; _workflow_to_dict restored (was accidentally dropped in rewrite — fixed).
- PROBLEM: workflow status stays "pending" forever — _run_workflow fire-and-forget task never runs or dies silently. DB rows stuck at pending. Log shows no orchestration traceback. Hypothesis: asyncio.create_task(self._run_workflow(db, workflow.id)) — db session passed is the outer request session; inside _run_workflow we open NEW session via get_session_factory() (fine), but the OUTER await db.flush()/commit happens after create_task returns... Actually create_workflow has `await db.flush()` then create_task then `_emit_workflow_event` then return — FastAPI's dependency get_db commits AFTER response? No — response is already sent, then get_db's `await session.commit()` runs. But we committed partially. The real issue may be: create_workflow's `await db.flush()` + then response — the workflow row IS committed later. That's fine.
- MORE LIKELY: get_db dependency generator commits after response but the workflow is already flushed (row exists). _run_workflow async task runs on event loop — should work. But check_phase4 creates workflows and polls 150s with none completing.
- NATS error recurring in log: "consumer is already bound to a subscription" in nats_client.py subscribe_agent_inbox (line ~198, js.subscribe reusing same durable consumer on nats_inbox_listener re-subscribe after worker restart?). Server restart → nats_inbox_listener restarts with same durable consumer name → JS error. Harmless for HTTP delivery but worker may crash? It except-passes? Check nats_inbox_listener code.
- NEXT DEBUG STEPS: add logging at start of _run_workflow; check if task created; the issue might be that _run_workflow raises early (e.g., select Workflow status 'pending' then set running — but workflow row may not be committed yet when task starts because db.commit hasn't happened (get_db commits after response)). Fix: commit BEFORE creating the task, or pass workflow_id and re-fetch with own session (we do re-fetch). If outer session not committed yet, our new session sees old status 'pending'... workflow IS committed (get_db commits after response send). BUT response is sent AFTER return of handler — the get_db.commit runs after response; task may start and re-fetch before commit → sees pending? Workflow is created with status pending already, so re-fetch finds it. Then sets running+commit. Should still work...
- Actually check: in _run_workflow first thing `if not workflow or workflow.status != "pending": return`. If re-fetch happens BEFORE outer commit: row exists (flush visible in same txn only). NEW session cannot see uncommitted row → workflow is None → returns early → workflow never runs! THAT'S THE BUG: re-fetch before outer commit sees None.
- FIX: either commit outer session before create_task (db.commit() then create_task) — but get_db will commit again (idempotent). Or don't re-fetch, just use status check after commit. Simplest: in create_workflow: await db.commit() (instead of flush) before create_task; keep get_workflow/list working.

## P4 state update 2
- Commit-before-dispatch fix applied; workflows STILL stay pending. So the _run_workflow task is not the issue OR it fails immediately. Next: instrument with logger to see what happens. Run: check backend log for any orchestration log lines. Suspect: _run_workflow imports `from app.models.task import Task` at module end — OK. Suspect 2: the task dies with exception swallowed by asyncio create_task default? create_task exceptions ARE logged to loop ("Task exception was never retrieved" printed to stderr/log). Check log for "Task exception" or "never retrieved".
- NATS fetch error in check script: 'JetStreamContext' object has no attribute 'fetch'. nats-py old API: use js.pull/subscribe or js.fetch requires... In nats-py, JetStream.fetch(stream=..., batch=...) DOES exist in recent versions. Error says no attribute — maybe `await js.stream_info` worked but `fetch` isn't exposed: use `js.pull(...)`? Actually correct: `await js.fetch(batch=n, stream="OAN_EVENTS")` is valid in nats-py >= 2.x. Maybe our installed version older. Alternative: subscribe with wildcard `oan.events.workflow.>` via nc.subscribe (core NATS — events are published to subject directly AND to stream; core subscribe on live stream works). USE: await nc.subscribe("oan.events.workflow.>", cb=...) with time.sleep(1) then count. Simpler + reliable.
- Workflow dispatch still failing: verify with curl after restart — POST workflow then GET after 10s check status.

## P4 state update 3
Check phase4: DAG validation PASS, create PASS, list PASS, no-host workflow terminates failed PASS. Remaining failures: (1) dispatch completes — workflow stuck "pending" forever; added logger + try/except around _run_workflow body with fail-safe marking workflow failed on exception — NEXT: restart server, rerun, check /tmp/backend.log for "Dispatch task starting" to see if task even runs. If it runs and fails, log shows why. (2) NATS events check: `nc.subscribe` requires coroutine cb — fix in check_phase4.py: `async def grab() -> int:` with callback as async def, then `await nc.subscribe(..., cb=grab_cb)`; wrap in asyncio.run. Simpler alternative: use JetStream js.pull? No — stick with subscribe + async cb.
Other facts: fake agent on :9444 needs heartbeat? Agents must be status=active for host resolution in _execute_step (Agent.status=="active"). check_phase4 does NOT heartbeat the fake agent → hosts empty → step fails w/ RuntimeError "No active agent found" → step failed → workflow fails/partial. BUT current DB shows pending not failed → dispatch never runs (pending). After adding logger, rerun and read log.
Also earlier run (before fake-agent active issue fix): steps failed with "Duplicate message" on retry — fixed via _attempt_message_id fresh uuid per attempt.
API tokens are in api_keys table (key_hash only; token only returned at registration).
Server restart cmd: kill $(pgrep -f "uvicorn app.main:app --port 8000"); cd backend; rm -rf app/__pycache__ app/services/orchestration/__pycache__; nohup env OPERATOR_SECRET=ops-secret uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 &
After P4 fixes pass: add frontend /workflows graph page? frontend has no workflows page yet — plan says workflow graph visualization desired; check page.tsx nav. Then commit+push Phase 4. Then Phase 5 (memory ACL), Phase 6 (marketplace tiers/metering/billing webhook), then final: pytest, e2e, schema audit, ROADMAP update, push.

## P4 state update 4 (critical findings)
Dispatch tasks DO enter (_run_workflow prints DISPATCH_ENTRY) but then nothing ever happens — no log lines at all after entry, and workflow status stays pending forever. DB query works fine from a standalone asyncio.run script (Workflow table query OK), so engine+driver fine. The hang is INSIDE the uvicorn server process's event loop task: after print flushes, the first `await session.execute(...)` never completes and never raises — yet other requests get served → the task is stuck in a blocked operation OR the print we see is from a task that's running on a DIFFERENT event loop (task created with wrong loop → never scheduled?). Actually uvicorn uses one loop; create_task uses running loop — fine.
NEW THEORY: `asyncio.create_task` was called inside a sync-ish spot? No, handler is async.
NEXT DEBUG IDEA: the task may be running but its prints go to the log... they don't appear. So the loop stops executing that task entirely → task cancelled by FastAPI? Uvicorn/Starlette may cancel remaining tasks on lifespan shutdown — but server stays up.
IMPORTANT CLUE: earlier run log showed `Task exception was never retrieved ... TypeError("'async_generator' object is not iterable")` at line 242 (deps loop `all(await ... for ...)` was the actual bug — fixed). BUT current runs show NO Task exception messages despite nothing happening. Wait — maybe 'Dispatch aborted' logger.info + print exist only in the if-block; print 'DISPATCH_ENTRY' is unconditional and appears. After it: `session_factory = get_session_factory()` sync; `async with session_factory() as session:` → async; then execute. If execute HUNG, other awaits would work (GET served) because hang is in asyncpg connection checkout? Pool size 20. Check pg_stat_activity from postgres for idle/active connections in state 'idle in transaction' piling up — if tasks are all waiting on connections that were never released (a previous task leaked a connection and transaction lock?) Actually asyncpg has statement cache issues with SQLAlchemy? Known: asyncpg + SQLAlchemy 2 + `expire_on_commit=False` fine.
ACTION: check `sudo -u postgres psql -c "SELECT state, wait_event_type, wait_event FROM pg_stat_activity WHERE datname='openagentnet';"` — look for lock waits on workflows table (maybe an uncommitted txn from dispatch holding row locks — but tasks print entry then hang at SELECT which needs no lock... UNLESS the session.execute triggers an implicit BEGIN and some other txn holds AccessShareLock? Unlikely).
Also consider: maybe the task IS running but print goes to log (shows) and then `workflow.status != "pending"` early-return... but we'd see status change. The abort logger line never appears.
ALTERNATIVE: the `async with session_factory() as session:` block — if get_session_factory's async_sessionmaker fails inside task (no loop-bound engine?), it would raise → Task exception logged. None logged.
=> Try adding prints after EACH line to pinpoint the exact hanging await.
Remaining check_phase4 failures: dispatch completes; no-host terminates (same hang); NATS events (nc.subscribe cb must be async coroutine — fix: `async def cb(msg): events.append(...)` + await nc.subscribe(cb=cb)).
Fake agent endpoint :9444 runs in check script — for real pipeline success, heartbeat the fake agent (heartbeat endpoint POST /agents/heartbeat needs Authorization: Bearer token of the agent). check_phase4.py should heartbeat fake agent after registration.
Then frontend: add workflows graph page? (optional) — then commit push P4.

## P4 state update 5 (worker approach ALSO hangs)
Check phase4 now: NATS events PASS (10 events), heartbeat PASS, DAG validation PASS, list PASS. Still failing: dispatch completes, no-host terminates.
KEY FINDING: background worker also hangs — `Workflow dispatch starting` logger line NEVER appears in log, pg shows the polling SELECT tasks.id=$1 idle-in-transaction (again) and UPDATE workflow_tasks idle-in-transaction from previous runs. So _run_workflow runs, executes UPDATE workflow_tasks (step.task_id set), then hangs at the poll-loop SELECT tasks. pg state idle + client has no pending query.
DECISIVE HYPOTHESIS: _execute_step's polling loop does `await asyncio.sleep(1)` then `await db.execute(select(TaskModel).where(TaskModel.id==...))`. The select returns task with status 'pending' (fake agent never reports). Loop continues. This should NOT hang pg (would repeat SELECT). But pg shows exactly ONE pending SELECT then idle... unless the loop exits the async with db without committing → fine. The REAL hang must be: the task is CANCELLED/dead. But worker is its own task... 
WAIT: check _execute_step again — after db.flush it does `deadline = datetime.now(UTC).timestamp() + MAX_STEP_RUN_TIME_SECONDS; while ... timestamp() < deadline: await asyncio.sleep(1); task_result = await db.execute(...)`. If step status becomes something... 
ALTERNATIVE: maybe the pg idle SELECT is from a DIFFERENT connection (NATS inbox forwarding worker SELECT tasks? inbox_forwarding_handler queries tasks?). Inbox forwarding handler likely does `select(Task)` for the forwarded task id — that's the idle SELECT! And UPDATE workflow_tasks from the engine task. The engine task itself may have moved on to asyncio.sleep waiting... pg idle = server done; Python polling fine, just sleeping. Check what the engine task's NEXT query would be: select Task — it repeats every 1s. pg shows only 1 such SELECT → engine task dead after first poll.
=> Add prints after EVERY await in _run_workflow to pinpoint, using a file writer (stderr in nohup works too). Print markers: E1 (session created), E2 (workflow found), E3 (status=running), E4 (order computed), E5 (before execute_step), E6 (inside poll loop, task status), E7 (loop done), E8 (commit done).
ALSO consider: _execute_step first line does `select(Agent.id).where(Agent.capabilities.contains(...))` — pg shows UPDATE workflow_tasks idle: that means engine got past find-hosts + send_message + flush. So hangs at poll SELECT or sleep.
If asyncio.sleep(1) hangs forever while other requests work → the task's event loop... tasks run on event loop; sleep hangs only if loop dead for that task — i.e. task cancelled or loop exception. But unawaited-exception logging absent...
Try: check if `asyncio.get_running_loop().time()` based tasks are scheduled — maybe the worker's task uses a different loop? asyncio.create_task in lifespan startup is fine.
Simplest decisive alternative: run _run_workflow logic synchronously with asyncio.run in a THREAD (threading + new loop) — guarantees isolation. If that works, the problem is uvicorn event loop task handling (maybe FastAPI/Starlette cancels non-BackgroundTasks tasks created during request; in the worker it's a lifespan task which shouldn't be cancelled — but it hangs too!). Actually worker's await OrchestrationService()._run_workflow(db, workflow_id) HANGS INSIDE THE WORKER TASK → the worker task never reaches await asyncio.sleep(2). Yet check script's "workflow dispatch completes" fails after 150s... and server still serves GETs. The worker task is one of MANY tasks; loop serves GETs while worker sleeps? If worker awaits _run_workflow forever, the 2s sleep never fires, but loop still serves. Consistent with pg: worker's db.execute SELECT pending (fine), then awaits _run_workflow, which inside does UPDATE (done, pg idle), then poll SELECT (done, pg idle), then asyncio.sleep(1) — sleep SHOULD resume in 1s. If it never resumes... THE TASK IS DEAD — likely Task was cancelled via... hmm. OR asyncpg connection issue: session.execute reuses same conn; maybe asyncpg connection in that session is broken (NATS error spam?) and execute raises but the raise goes where? Worker loop `try/except Exception` logs it — NO error in log.
Try one more thing: reproduce with minimal: standalone script calls _run_workflow directly via asyncio.run in-process → earlier wftest hangs too... test: import OrchestrationService, create pending workflow in DB manually, run asyncio.run(OrchestrationService()._run_workflow(db, id)) in a fresh script — see where it hangs with prints. If it hangs there too, the issue is in _run_workflow code itself (e.g. an await that blocks the whole loop = sync code inside async?). 
Actually — REVELATION: `messaging = MessagingService()` then `await messaging.send_message(db, envelope, ...)` — send_message does publish_to_agent which does `nats.publish` — if NATS connection broken, publish awaits forever? nats-py publish is async... if server closed, publish may raise. Hmm but NATS IS up (events published!).
Check inbox forwarding handler — it does await db.execute SELECT tasks for forwarded envelope — could that be a different query.
NEXT: add marker prints E1-E8, rerun, see which marker appears.

## P4 state update 6 — CRITICAL: dispatch STILL stuck pending even after all fixes
check_phase4 progress: NATS events PASS (50 now!), heartbeat PASS, DAG validation 3x PASS, list PASS, no-host test FAILS (workflow stays pending instead of failed). Workflow dispatch completes FAIL.
Facts established:
1. Markers M1-M5 prove engine runs: session opens, workflow→running, step executes, dispatches task, poll loop runs every 1s.
2. /messages/{id}/result endpoint works and fake agent auto-reports after 0.3s (thread).
3. Poll loop in _execute_step exits when task.status in terminal; task reports via FAKE_AGENT_TOKEN (Bearer) — BUT _report uses FAKE_AGENT_TOKEN set at registration time; heartbeat endpoint works.
4. Worker dispatch picks pending workflows every 2s; stale pending workflows (wf-repro, phase4-pipeline, no-host-pipeline) keep getting retried — wf-repro still pending means engine retries forever?? M5 markers appeared only ~8 times in wf3 run (which only waited 20s); then engine must time out after 30s and set step.failed → workflow.failed... BUT wf-repro STILL pending after minutes across worker restarts!
WAIT: workflow_dispatch_worker runs _run_workflow; on first run workflow pending→running, then timeout → except block marks workflow failed + emits event. BUT next worker iteration select pending finds nothing. Yet DB shows wf-repro pending forever. => _run_workflow's try block succeeds?? No exception → workflow stuck at 'running'? But DB shows 'pending' not 'running'!! Status stays 'pending' meaning engine never sets running?? Marker M2 printed AFTER setting running... In wf3 run M2 printed. But DB wf-repro pending. Contradiction unless engine runs on a DIFFERENT wf copy... 
KEY REALIZATION: maybe the 'running' update + flush happened but the session later ROLLED BACK (exception in commit)? The except block marks failed w/ new session. If engine throws before setting running... no.
ALTERNATIVE: the dispatch worker is NOT running! Check /tmp/backend.log for "Workflow dispatch starting" in latest run — grep earlier showed NOTHING in latest runs. The worker may be hanging at `await OrchestrationService()._run_workflow(...)` for the FIRST pending workflow (wf-repro from wftest!) — blocking all subsequent dispatches! wftest ran BEFORE server restart? No — wftest ran after old server with old code... After restart, wf-repro pending from BEFORE. Engine picks it, runs... and hangs (as before — poll loop forever?). Markers M5 appeared in wf3 run. But then engine MUST time out after 30s. Unless... MAX_STEP_RUN_TIME_SECONDS=120 was compiled-in for that run (I changed to 30 later, and the last check_phase4 run used 30s timeout but workflows STILL pending after ~90s total runtime).
=> CHECK: does wf-repro engine ACTUALLY time out? Add marker for timeout/except. Also check what happens to wf-repro's tasks table: task status?
NEXT STEPS: (a) inspect tasks row for wf-repro's dispatched task — status success/pending? (b) if status pending in tasks: fake agent report FAILED (401? token invalid because wftest's fake agent token differs from FAKE_AGENT_TOKEN? In wftest, fake agent registered fresh — report uses that token; BUT wftest doesn't run check script's fake server... wftest creates its own agent w/o server! wftest task has no executor — times out → step failed → workflow failed. Yet pending... (c) the worker's session.execute select(Workflow.id).where(pending) — wf-repro pending; engine sets running (flush not commit!) then hangs on... poll loop sleep — BUT pg showed poll SELECT idle-in-transaction... if engine thread of the poll loop is alive and looping, pg would show repeated SELECTs. Single idle SELECT means engine died mid-poll-loop: task cancelled.
FINAL TEST: run check_phase4 alone on fresh server WITH markers/logs; after it ends, check wf-repro-equivalent status + log lines "Workflow dispatch starting" + "executing step" + timeout markers. If dispatch started and step logged but no timeout marker → sleep/execute in poll loop hangs permanently → asyncio event loop issue specific to this server process. Try: patch _execute_step poll loop to use sync sleep via time.sleep in thread? Hack. Or use threading-based dispatch (thread + asyncio.run) for the engine to guarantee loop isolation.
NOTE for report endpoint: requires Authorization with valid token of participant — fake agent's token works for /messages/{mid}/result? Earlier test with nonexistent token → 401; didn't test with real token.

## P4 state update 7 — ROOT CAUSE FOUND + partially fixed
ROOT CAUSE of stuck-pending workflows: TWO bugs in _run_workflow:
1. Lines 230-232 (before fix): `workflow.status = "running"; await session.flush()` were OUTSIDE the `async with session_factory() as session:` block (the `async with` closed right after the pending check). So running-status never flushed, workflow stayed 'pending' forever, worker re-picked it every 2s, re-executed the whole engine. Each run added... well steps already existed; but engine's select(WorkflowTask) used `scalar_one_or_none()` — with MULTIPLE stale duplicate rows (multiple check runs' workflows? no — duplicates per workflow e.g. phase4-pipeline 30 rows = 6 check runs × 5 steps, wf-repro 2 rows = 2 wftest runs) → MultipleResultsFound → engine threw → status never updated → stuck pending forever.
FIXES DONE:
- model: WorkflowTask now has UniqueConstraint(workflow_id, node_id)
- migration 007_workflow_task_unique_constraint.py written (prunes duplicates + adds constraint)
- _run_workflow: whole engine body moved INSIDE async with block (node_map still needs re-indent +4)
- engine claims workflow with `select(Workflow).with_for_update()` so concurrent iterations skip
STILL TODO:
- re-indent lines 243-331 by +4 spaces (the for-loop body and aggregation block)
- apply migration 007, restart server, re-run check_phase4.py
- also note: worker workflow_dispatch_worker in app/core/workers.py runs OrchestrationService()._run_workflow — with the atomic claim this is now safe.
- After check passes: run pytest from repo root (python3 -m pytest), e2e_test.py (redis flush first), frontend build (pnpm build), commit+push P4.
- P4 remaining items: optional workflows frontend page; ROADMAP update; notes.
- Env: repo /home/ubuntu/OpenAgentNet, server: cd backend && nohup env OPERATOR_SECRET=ops-secret uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 &, kill via pgrep -f uvicorn. Redis: redis-cli FLUSHDB. DB: postgresql://openagentnet:openagentnet@localhost:5432/openagentnet, alembic in backend dir. Git push: git -c user.name="vincenzo-afk" -c user.email="itsmebk2007@gmail.com" commit -am "..." && git push origin main
- check_phase4.py now passes: heartbeat, DAG validation, NATS events (50!), list. Needs dispatch completes + no-host failed after fixes.

## P4 state update 8 — engine silently dies; switching to thread-isolated dispatch
Current state (fresh server restart PID 21028, /tmp/backend.log has 649 lines, mostly NATS "consumer already bound" spam from nats_inbox_listener every 15s which is harmless noise):
- Migration 007 applied successfully (unique constraint on workflow_tasks, duplicates pruned).
- Fixes done so far: (a) full engine body inside async-with session block; (b) FOR UPDATE claim; (c) `_gsf()()` double-call fix in except handler; (d) MAX_STEP_RUN_TIME_SECONDS = 30.
- check_phase4 result: ALL pass except 'workflow dispatch completes' and 'no-host workflow terminates as failed/partial'.
- no-host-pipeline pending 8 min, BOTH steps have task_id NULL → engine fails BEFORE _execute_step, and produces NO 'engine failed' log (grep count = 0). Workflow status never changed from pending → worker keeps re-picking it (FOR UPDATE claim should prevent concurrent claim, but worker loop retries same wf every 2s: claim succeeds after abort because status still pending!).
- The engine coroutine dies silently: no exception logged. This is classic "task was cancelled and cancellation swallowed" OR the exception happened in the except-handler cleanup (_gsf() missing call BEFORE my fix — Fixed now, but old code may still be running? No—server restarted).
- NATS spam every 15s: nats_inbox_listener retries subscribe_agent_inbox('+') and JetStream says consumer already bound. Harmless but noisy; consider fixing: only subscribe once (check is_nats_available + flag).
DECISION: Rewrite dispatch worker in app/core/workers.py to run the engine in an ISOLATED synchronous thread with its own event loop:
    def _dispatch_isolated(wf_id):
        asyncio.run(OrchestrationService()._run_workflow_sync(wf_id))  # or import AsyncSession via sync? 
Simpler: add `run_engine(wf_id)` that creates AsyncSession with engine + does everything via sync-friendly asyncio.run. `_run_workflow` must become async-only and self-contained (it already creates its own factory). So worker just does:
    from concurrent.futures import ThreadPoolExecutor
    executor.submit(asyncio.run, service._run_workflow(None, wf_id))  # _run_workflow builds its own factory
That fully isolates each dispatch from uvicorn loop and any pending transaction state.
ALSO add: in worker, set workflow status to 'dispatching' (running) BEFORE handing off, via a single UPDATE, to prevent retry loops; or accept retries (engine skips non-pending) but that requires commit before handoff → do commit in worker after setting running.
ALSO fix nats_inbox_listener noise: add `_subscribed` flag so it doesn't re-subscribe.
ALSO check_phase4.py remaining fix: polling deadline may be too short vs 30s step timeout × retries; it's 150s so fine.
After fix: restart, check phase4, then pytest (python3 -m pytest from repo root), e2e_test.py, frontend build, ROADMAP update P4, commit push.

## P4 state update 9
- Thread-isolated dispatch (asyncio.run in ThreadPoolExecutor) STILL fails — log grew to 608776 lines with "Workflow dispatch engine failed" repeating every 10s for many old workflow ids. The engine itself throws. Need to capture the FIRST inner exception: the except-handler logs 'engine failed' with traceback — my last greps only showed tail. Grep the FIRST occurrence in a FRESH run (clear log, restart, run check, then look at line after first 'engine failed' — full traceback printed by logger.exception).
- Heartbeat 404 in check_phase4: endpoint is POST /v1/agents/{id}/heartbeat — check_phase4 BASE may be http://localhost:8000/registry or missing /v1? Actually e2e heartbeat URL was /registry/agents/... Check BASE in check_phase4 (line ~30): if BASE="http://localhost:8000/registry" then /agents/{id}/heartbeat → /registry/agents/... which is correct? 404 means wrong. e2e_test.py uses BASE+"/registry/agents/{id}/heartbeat"? Need to check. Earlier run (before my edit) heartbeat PASSED — wait update 8 showed [PASS] fake agent heartbeat! After worker edit, heartbeat 404?? Odd — I only edited workers.py. Unless redis FLUSHDB flushed nothing affecting... No — maybe server start race: curl before startup. Actually heartbeat ran right after registration; server was up. Hmm but result showed 404. Check the check script URL vs e2e.

## P4 state update 10 — FINAL root cause identified
Error: "got Future attached to a different loop" in asyncio.run isolated thread. asyncpg connections are bound to the MAIN loop (created via get_engine shared), so reusing them from a new loop fails.
FIX: write a fully SYNC dispatch path: sync_psycopg Session, sync SQLAlchemy queries, sync time.sleep, sync NATS publish (nats-py has sync client? NO). NATS event emission: optional — emit via a helper that creates fresh async loop? Simplest: skip NATS in sync path? No — keep events: run publish via asyncio.run_coroutine_threadsafe(nats_client publish, MAIN_LOOP). Capture MAIN LOOP handle (asyncio.get_running_loop at startup) and use run_coroutine_threadsafe to emit NATS events from the sync engine.
Simplest robust: convert _run_workflow to sync def using sync Session (psycopg) and sync sleeps; NATS events via run_coroutine_threadsafe against main loop reference. Main loop ref: store asyncio.get_event_loop at worker creation time (workers run on main loop).
Then workflow_dispatch_worker = threading worker pool calling the sync engine directly (no asyncio.run).
Keep async _run_workflow? Remove it; replace with _run_workflow_sync(wf_id). Handler create_workflow keeps POST-only registration.

## P4 state update 11 — design decision: main-loop dispatch queue
Confirmed error (fresh run /tmp/backend.log first traceback): "RuntimeError: Task got Future attached to a different loop" at session.execute() — asyncpg connections bound to main loop, cannot be used from asyncio.run in a worker thread.
DESIGN (final): Main-loop dispatch queue — no threads, no cross-loop futures.
1. In orchestration/service.py: add module-level `dispatch_queue: asyncio.Queue = None` (create lazily), async def `dispatch_workflow(workflow_id)` which puts wf_id into queue. In create_workflow API handler, replace fire-and-forget with `await OrchestrationService.dispatch_workflow(str(workflow.id))` (synchronous enqueue, fine).
2. In core/workers.py: workflow_dispatch_worker becomes: pick pending ids from DB (sync query via main-loop session), enqueue each into dispatch_queue, then `for id in pending: await service._run_workflow(id)`?? NO — _run_workflow is long-running; instead start one async task PER workflow using `asyncio.create_task` at startup? The original fire-and-forget DID die silently...
REVISIT the original hang evidence: DISPATCH_ENTRY printed → engine started → hang. That WAS on the main loop (fire-and-forget inside request handler runs on main loop too). So main-loop hypothesis fails to explain the original hang.
=> Root cause of ORIGINAL hang may be DIFFERENT: maybe messaging.send_message deadlocked waiting on NATS publish while NATS connection is busy (consumer already bound spam)? Or the check script's fake agent server: send_message sends to agent endpoint (HTTP) — fake handler receives, replies 200, then _report thread calls /messages/{id}/result. The engine poll sees task success → fine. But no-host case: no active host → RuntimeError → retries 3x × 1s → step failed → workflow failed. Should terminate in seconds.
=> What if BOTH bugs apply: original hang = MultipleResultsFound swallowed (engine failed log WAS absent because... it DID log — earlier grep showed "Workflow dispatch engine failed" lines!). Yes! Original run: engine failed MULTIPLE TIMES (we saw 608k log lines), status never updated (PendingRollbackError in cleanup), workflow stayed pending. That's why it looked like a hang. The fix of migration 007 + _gsf()() call should have fixed everything...
BUT in fresh run after fixes: engine fails at first select with "Future attached to a different loop" — ONLY in the thread worker variant. The original main-loop variant (create_task) should work now with 007+for_update fixes.
=> NEW PLAN: REVERT workers.py dispatch to main-loop variant BUT not per-request create_task: keep worker loop, but inside main loop, do `asyncio.create_task(OrchestrationService()._run_workflow(None, wf_id))` — same main loop. The earlier silent death of create_task in handler may have been due to MultipleResultsFound + PendingRollbackError combo AND the _gsf() bug in cleanup; BOTH fixed now.
ALSO the worker must avoid re-submitting the same pending wf every 2s: use a set `dispatching` (wf_id -> task) keyed on task.done(); skip if already dispatched.
IMPLEMENT:
- workers.py workflow_dispatch_worker: revert to main-loop create_task approach + in-flight set.
- Revert nats_inbox_listener _subscribed change? Keep it (harmless, reduces noise).
- Ensure _gsf()() fix stays.
- Also: engine cleanup except sets failed + emits event — good.
REMEMBER: re-run: kill server, clear pycache, restart, redis FLUSHDB, run check_phase4.py.
