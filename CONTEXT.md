# CONTEXT.md — decisions, plan and changes

Append-only log. Newest entries at the bottom of each section. Dates are absolute.

## Goal

Portfolio project for a "Software Engineer, Data Platforms" role at a human-data / RL-environment
company. Must demonstrate: FastAPI, React/TypeScript, PostgreSQL + MongoDB, GCP deployment,
CI/CD, access control, client data exports, agent loops, MCP, RAG, evals.
Target: public launch ~2026-11-27 (2-week plan from 2026-11-13).

## Product

**RewardHacker — "Red-team your rewards."** Probes RL coding tasks (Terminal-Bench / Dynamo
style) for loopholes: free reward, broken references, flaky verifiers, tamperable verifiers,
and task-specific shortcuts found by an LLM adversary. Robustness score + verdict + fixes.

## Stack decisions

| Area | Decision | Why |
|---|---|---|
| Core | Python 3.12, uv, pydantic, typer + rich | |
| Sandbox | Docker CLI via subprocess | no native deps, works on Windows |
| LLM | Gemini (`gemini-3.1-flash-lite` default) via `google-genai` | user has a paid Google key |
| Backend (day 6) | FastAPI + SQLAlchemy + Alembic + PostgreSQL | |
| Traces / guidelines | MongoDB Atlas free tier | document-shaped data; RAG vector search |
| Frontend (days 7–8) | React + TypeScript + Vite | |
| Cloud (days 11–12) | GCP free tier: Cloud Run (API + web), e2-micro VM (Docker worker), GCS (exports), Secret Manager; Postgres on Neon free tier | Cloud Run cannot run Docker-in-Docker; Cloud SQL not free |
| CI | GitHub Actions: ruff, unit tests, Docker LoopBench | |

## Constraints

- LLM budget ≈ ₹800 total (~$9). Per run $0.05, per day $0.50, enforced in code.
- GCP: free tier only; budget alert ~₹100 as a safety net.
- Repo private until launch, then public. Author = Sagolsem Gegarin Singh; keep the Claude
  co-author trailer.

## Two-week plan

| Days | Milestone | Status |
|---|---|---|
| 1–2 | task.yaml, sandbox, null/reference/flaky probes, CLI | done 2026-11-13 |
| 3 | tamper probes, LoopBench ~10 tasks, `rh bench` | done 2026-11-13 |
| 4–5 | Gemini adversary + judge, spend caps | done 2026-11-14 (live: LoopBench 12/12) |
| 6 | FastAPI backend: auth, orgs, roles, task upload, runs, job queue; traces → MongoDB | done 2026-11-14 |
| 7–8 | React dashboard: reports, trace viewer, reviewer triage | done 2026-11-14 (triage deferred) |
| 9 | GCS exports (signed URLs), audit log, API keys, RAG spec check vs guidelines | done 2026-11-14 (GCS path unverified until deploy) |
| 10 | MCP server | done 2026-11-15 |
| 11–12 | GCP deploy, CI/CD, observability | |
| 13 | LoopBench complete; run on public benchmarks; write up results | |
| 14 | README, demo video, go public | |

## Decision / change log

- 2026-11-13 — Project chosen over alternatives (Meitei data platform, BugHarvest, Provenance)
  for best fit with RL-environment work. Name: RewardHacker.
- 2026-11-13 — Task format modelled on Terminal-Bench / Dynamo: tests copied in at verify time.
- 2026-11-13 — Tamper findings are collapsed into `null-passes` when the verifier passes with no
  work (same root cause); the adversary is skipped in that case (saves money).
- 2026-11-13 — **Key finding:** with a root agent no in-container verifier is trustworthy
  (`.pth` hook beats `python -I`; lingering process rewrites tests after copy-in). Added
  `environment.agent_user` / `verifier.user`; hardened LoopBench tasks run the agent unprivileged.
- 2026-11-13 — Adversary is **black-box** (sees objective + environment, not tests); a judge call
  separates genuine solutions from shortcuts. White-box would flag every task via hard-coding.
- 2026-11-13 — Default model `gemini-3.1-flash-lite` ($0.25 in / $1.50 out per 1M tokens, per
  ai.google.dev pricing page); 2.5 Flash-Lite cheaper but reportedly near end-of-life. Exact
  model ID still to be verified against the live API.
- 2026-11-13 — google-genai is an optional extra (`rewardhacker[llm]`); core works without it.
- 2026-11-14 — Model ID `gemini-3.1-flash-lite` verified against the live API (also listed:
  `gemini-2.5-flash-lite`, `gemini-3.5-flash-lite` — pricing for 3.5 unchecked, not adopted).
- 2026-11-14 — First live run: Flash-Lite ignored "don't solve" and computed the real answer
  (judge: genuine → weak verifier missed). Fix: prompt now demands *deliberately wrong* output
  ("a pass only matters if your work is wrong") and repeats it in the first user message.
  After fix: `weak-output-check` → `total: 0` shortcut, EXPLOITABLE; `rh bench --adversary
  required` 12/12. Cost: ~$0.001–0.003 per adversary run; $0.0072 for the whole day.
- 2026-11-14 — Day-6 databases: Neon Postgres (AWS Singapore, PG 18) + MongoDB Atlas M0
  (cluster "Gegarin"), used from local dev too (user's choice over docker-compose). Env vars
  `DATABASE_URL`, `MONGODB_URI`.
- 2026-11-14 — Day-6 backend design: JWT (HS256, `RH_JWT_SECRET`) + Argon2 (pwdlib); roles
  viewer < reviewer < admin per org; non-members get 404 (no org enumeration); org must keep
  one admin. Job queue = `runs` table claimed with `FOR UPDATE SKIP LOCKED` (no broker);
  `recover_stale` requeues runs stuck >1h, fails after 3 attempts. Runs are static-only unless
  `include_llm=true`. Adversary steps → Mongo `traces`; Postgres report keeps everything else;
  if Mongo is down the steps stay inline in the report. Uploads = .zip, extracted with
  zip-slip/symlink/bomb checks to local disk (GCS on day 9). Tests: SQLite + MemoryTraceStore.
- 2026-11-14 — Live E2E (Neon + Atlas + Docker + Gemini): upload → queue → `rh worker --once`
  → EXPLOITABLE, `adversary-shortcut`, trace in Atlas; $0.0016. Left one `e2e-*@example.com`
  user + "E2E org" in Neon.
- 2026-11-14 — Known risk: uploaded tasks' Dockerfiles are built on the worker (`docker build`
  has network access). Acceptable for invited orgs; revisit before opening public sign-up.
- 2026-11-14 — Dashboard design brief (user's picks): "modern SaaS" feel, references Linear +
  Vercel dashboard, light + dark toggle, one violet accent (#6d28d9 / #8b5cf6), Geist + Geist
  Mono (self-hosted via @fontsource), wordmark + "broken checkmark" logo designed in-house.
  Colour otherwise only encodes verdict/severity. Public landing page included; its hero is a
  real adversary trace (weak-output-check), not a mock-up. Verified with Playwright at
  1440px and 390px, light + dark: no horizontal overflow, fonts load.
- 2026-11-14 — Seeded a demo account in Neon (`demo@rewardhacker.dev`, org "Acme RL
  Environments", 4 LoopBench tasks + real runs). Password is only in the session scratchpad;
  reset by re-registering a new demo user if needed.
- 2026-11-14 — Day 9 design: `require_role` returns a `Principal` (member or org API key);
  keys are `rh_` + 256-bit random, stored as SHA-256, role viewer/reviewer only, bound to one
  org, rejected on member/key/audit management and `/me`. Audit events are written in the same
  transaction as the change they record. Exports are built synchronously (small orgs) and
  served via 15-min links: HMAC-signed API route locally, GCS V4 signed URLs when
  `RH_GCS_BUCKET` is set (GCS path written but not yet run against a real bucket).
- 2026-11-14 — RAG spec check: guidelines chunked by heading, embedded with
  `gemini-embedding-001` (768-d, re-normalised; $0.15/1M tokens, usage estimated at 4 chars/
  token since the API reports none), stored in Mongo `guideline_chunks`; Atlas Vector Search
  index `guideline_vectors` (READY, filter on org_id) with brute-force cosine fallback. One
  `complete_json` call cites excerpt numbers. Live: weak-output-check → 1 high issue (format-only
  test); strong-output-check (probes: ROBUST) → hard-coded expected total matches visible data
  (breaks "include an unseen case"): the spec check catches things the probes can't. ~$0.0005
  per check. Example guidelines in `examples/guidelines/` (written for this project).
- 2026-11-15 — MCP server (`rh mcp`, stdio) built on the official Python SDK **v2** (`mcp>=1.9`
  resolved to 2.3: `FastMCP` is now `mcp.server.mcpserver.MCPServer`, client is `mcp.Client`).
  Design: thin REST client with an org API key (new `GET /api/auth/key` tells it its org/role),
  so roles + audit log apply unchanged; 10 tools return Markdown; task refs accept full id,
  8-char prefix or task.yaml id. Tests drive the real protocol in-process (`Client(server)`)
  against the FastAPI TestClient. Live: spawned over stdio → whoami, list_tasks, start_run
  (wait) on broken-reference → BROKEN in 26s via a real worker. Demo org now has an API key
  "Claude Code (MCP)" (raw key only in the session scratchpad).
- 2026-11-15 — Windows: a running `rh serve` locks `.venv/Scripts/rh.exe`, which breaks
  `uv add/sync`. Run long-lived dev processes as `uv run --no-sync python -m uvicorn ...` /
  `python -m rewardhacker.cli worker` instead.
- 2026-11-22 — GCP project `rewardhacker` created (billing linked; gcloud installed and logged
  in on the user's machine). Cost guards before any deploy: (1) console spend cap
  `RewardHackerBudgetCap`, Cloud Run only, ₹150 (GCP native caps allow one project + one
  service); (2) budget `rewardhacker-kill-switch` (all services, ₹150) → Pub/Sub `billing-cap`
  → function `billing-kill-switch` (us-central1) that unlinks billing at 100%. Dry-run
  verified; the real unlink path is not exercised. See `infra/billing-kill-switch/README.md`.
  An account-wide `BudgetCap` (₹1000, alerts only) also exists.
- 2026-11-22 — **Worker = Cloud Build per run** (user's choice after weighing JD fit: always-on,
  ₹0, per-job isolation). An always-on e2-micro was rejected: its external IPv4 (~$3.60/month)
  is not in the free tier and would trip the ₹150 kill switch. Queueing a run (or viewing one
  queued >90 s) kicks `rh worker --once --idle-exit 45` as a Cloud Build job (worker image,
  `rh-worker` SA, secrets via availableSecrets); ≤2 concurrent builds, kicks throttled. Cloud
  Build free tier: 2,500 min/month on e2-standard-2. Local `rh worker` still works alongside.
- 2026-11-22 — Cloud Run: one service serves API + dashboard (RH_WEB_DIR); uploads stored as
  zips in `gs://rewardhacker-data-289475076247/tasks/` and extracted into a local cache by
  readers (API and worker share no disk). GCS V4 signed export URLs verified live (IAM signBlob
  with a cloud-platform-scoped token; `rh-api` has TokenCreator on itself only).
- 2026-11-22 — Daily LLM cap moved to MongoDB (`llm_spend`, one doc per UTC day, `$inc`); the
  JSON-file ledger silently reset on Cloud Run / per-run builds. Fails closed.
- 2026-11-22 — **Bug fixed (found in the cloud E2E):** when the adversary could not run (ledger
  unreachable → budget refusal) the run was reported ROBUST/100. Now `Probe.trial_error` marks
  such a probe `error`, and any errored probe makes the verdict `inconclusive` (findings still
  win). Regression tests added.
- 2026-11-22 — Kill-switch monitoring: error/critical log alert, 6-hourly scheduled self-test
  (incl. IAM testIamPermissions for deleteBillingAssignment), absence alert after 13 h, all to
  the owner's email. See `infra/billing-kill-switch/README.md`.
- 2026-11-22 — Atlas IP access list opened to 0.0.0.0/0 (Cloud Run/Cloud Build have no static
  egress IPs; M0 has no private endpoints; auth still required). Cluster is AWS Mumbai
  (ap-south-1). Final cloud E2E: EXPLOITABLE, trace stored, spend ledger updated.
- 2026-11-22 — CD: `deploy` job in ci.yml after test+web on pushes to main. Keyless auth via
  Workload Identity Federation (pool `github`, provider `github-repo`, condition: this repo +
  refs/heads/main) → `rh-deployer` (AR writer on the repo, run.developer on the service,
  actAs rh-api). Images tagged by commit SHA; `/api/health` reports `commit`; smoke test, then
  automatic traffic rollback to the previous revision on failure. Docs: `deploy/README.md`.
- 2026-11-23 — **Gemini cost exposure closed.** The Gemini key lives in project "RewardHack"
  (`gen-lang-client-0379661206`), outside the ₹150 kill switch. (1) Cloud daily LLM cap $0.10
  (`RH_DAILY_BUDGET_USD`), now also forwarded to Cloud Build workers (they used the $0.50
  default). (2) Budget "gemini-key-RewardHack" ₹200/month, alerts 25/50/90/100 % + forecast.
  (3) Paid AI features (LLM runs, guidelines, spec checks) are per-org opt-in: `orgs.llm_enabled`
  (migration c4e1a9d27b30, Neon migrated), `RH_NEW_ORGS_LLM=0` on Cloud Run (default on for
  local dev), 403 otherwise; operator toggles with `rh llm-access [<org-id>] [--off]`. Demo org
  "Acme RL Environments" enabled. Dashboard greys out AI controls with an explanation.
- 2026-11-23 — Day 13: `rh import-tb` converts Terminal-Bench 1 (harbor-framework/terminal-bench-1
  @ d28711d, Apache-2.0) tasks: 198 of 241 imported, 43 skipped with reasons (multi-container,
  solution.yaml-only, Dockerfile bakes in tests, unsupported compose options). Faithful mapping:
  agent = root, `run-tests.sh` unchanged, network on. New `environment.network: none|bridge`
  (default none); bridge needs `RH_ALLOW_TASK_NETWORK=1` (sandbox guard) and is always refused
  for web uploads. Imported tasks live in git-ignored `benchmarks/` (TB canary: never commit).
- 2026-11-23 — **Run caps (cost).** `RH_RUNS_PER_ORG_PER_DAY=20` and `RH_RUNS_PER_DAY_TOTAL=100`
  (rolling 24 h, 429 + Retry-After, 0 = off) so API keys/scripts can't burn Cloud Build minutes.
  Soft cap: concurrent requests at the limit can both pass.
- 2026-11-23 — **UI: "Ember" theme.** User picked draft B of three HTML mockups (kept on the
  Desktop in `rewardhacker-templates/`). Cream `#FBF6EF`, espresso `#2B1D14`, ember `#E8590C`
  (display/decoration) with `#CC4A0A` for button fills (AA with white text); Sora + Martian Mono
  via @fontsource; pill buttons, round markers; landing page = hero + ticket, sticky scroll story,
  verdict strip, ember closer. Dark mode = espresso palette. Frontend only; routes/API unchanged.
