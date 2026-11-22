# HANDOFF.md — where we left off

_Last updated: 2026-11-22 (day 11: Cloud Run + Cloud Build workers deployed)_

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

- Live: https://rewardhacker-289475076247.us-central1.run.app (Cloud Run `rewardhacker`,
  image `api:v4`; API + dashboard). Workers: Cloud Build per run (`worker:v2`), dispatched by
  the API. Bucket `gs://rewardhacker-data-289475076247`. Secrets in Secret Manager (prod JWT
  secret is NEW, different from .env). SAs: `rh-api`, `rh-worker`, `billing-kill-switch`.
- Cost guards + monitoring: see `infra/billing-kill-switch/README.md` (₹150 cap, self-test
  every 6 h, email alerts).
- gcloud in this shell: prepend `/c/Users/sagol/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin`.
- **BLOCKED on the user:** MongoDB Atlas Network Access must allow GCP egress (0.0.0.0/0;
  M0 has no private endpoints). Until then traces + the LLM spend ledger fail from the cloud,
  so LLM runs come back `inconclusive` (by design: fail closed). After that: rerun the LLM E2E
  (scratchpad script `e2e_dispatch.py` → expect EXPLOITABLE + traces).
- Test data in Neon: a few `e2e-cloud-*@example.com` users + "E2E cloud org".

## Next steps (in order)

1. Day 12: CI/CD deploy job (GitHub Actions → build api/worker images → Cloud Run), structured
   logs/observability, then the Atlas-dependent LLM E2E. (Day 11 deploy done; old plan:) Plan: Cloud Run (API + static web), e2-micro VM (Docker worker, free
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
