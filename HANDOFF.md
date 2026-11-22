# HANDOFF.md — where we left off

_Last updated: 2026-11-22 (days 11–12 core done: cloud deploy + CD from GitHub Actions)_

## State

- Days 1–10 of the plan are done (see `CONTEXT.md` → Two-week plan). Private repo
  `GegarinSagolsem/rewardhacker`, branch `main`.
- Probing engine: 9 probes; LoopBench 12/12 with the live Gemini adversary.
- Backend: FastAPI (auth, org roles, uploads, Postgres job queue, Mongo traces, audit log, API
  keys, exports, guidelines + RAG spec check). Neon schema at Alembic `81fb72ee86e3`.
- Dashboard (`web/`): all pages incl. Guidelines, API keys, Activity; Playwright-checked.
- **MCP server (day 10):** `rh mcp` (stdio), 10 tools, org-API-key auth, verified live over
  stdio with a real worker. Config example: `examples/mcp/.mcp.json`, README section "MCP server".
- Tests: 54 fast Python tests (core, adversary, api, api_data, mcp) + Docker LoopBench; web lint
  + tsc + build in CI.
- Gemini spend so far: ≈ $0.013 total.
- Local dev processes: run as `uv run --no-sync python -m uvicorn rewardhacker.api.app:create_app
  --factory --port 8000` and `uv run --no-sync python -m rewardhacker.cli worker` (see CONTEXT.md:
  `rh.exe` locking on Windows).

## GCP status (2026-11-22)

- Live: https://rewardhacker-289475076247.us-central1.run.app (Cloud Run `rewardhacker`;
  API + dashboard). Workers: Cloud Build per run. **Deploys are automatic**: push to main → CI →
  `deploy` job (images tagged by SHA, `/api/health` shows the live commit, auto-rollback); see
  `deploy/README.md`, dispatched by
  the API. Bucket `gs://rewardhacker-data-289475076247`. Secrets in Secret Manager (prod JWT
  secret is NEW, different from .env). SAs: `rh-api`, `rh-worker`, `billing-kill-switch`.
- Cost guards + monitoring: see `infra/billing-kill-switch/README.md` (₹150 cap, self-test
  every 6 h, email alerts).
- gcloud in this shell: prepend `/c/Users/sagol/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin`.
- Atlas Network Access opened to 0.0.0.0/0 (2026-11-22, by the user). Full cloud E2E passes:
  upload → Cloud Build worker (auto-dispatched) → weak-output-check EXPLOITABLE, trace in
  Atlas, $0.0018 recorded in the shared Mongo ledger (`llm_spend`).
- Test data in Neon: a few `e2e-cloud-*@example.com` users + "E2E cloud org".

## Next steps (in order)

1. Day 12 rest: observability (structured JSON logs for API + worker with run ids, an uptime
   check / error alert for the API), maybe hide the score on inconclusive runs. Then day 13–14.
   (Old deploy plan, for reference:) Plan: Cloud Run (API + static web), e2-micro VM (Docker worker, free
   tier), GCS bucket for exports (verify `GCSExportStore` signed URLs for real), Secret Manager
   for keys, Neon + Atlas stay; open Atlas network access for Cloud Run egress; GitHub Actions
   deploy job; basic observability (structured logs, health checks).
2. Optional: register the MCP server in the user's own Claude Code and record a short demo.
3. Small follow-ups: reviewer triage on findings; the 4 react-refresh lint warnings.

## Open questions / risks

- Uploaded task Dockerfiles are built on the worker with network access (see CONTEXT.md).
- Spec-check quality depends on the guidelines and one Flash-Lite call; it can over-report.
- The judge is the same model as the adversary; consider a stronger judge later.
- e2-micro (1 GB RAM) may be tight for Docker builds; fall back to running the worker locally
  for the demo if needed.
