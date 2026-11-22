# HANDOFF.md — where we left off

_Last updated: 2026-11-22 (day 11 in progress: GCP project + cost guards)_

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

- Project `rewardhacker` exists, billing linked, `gcloud` installed + logged in (in this shell,
  prepend Machine+User PATH first: the session may predate the install).
- Cost guards are live: Cloud Run spend cap (₹150) + all-services kill switch (₹150 →
  unlink billing). See `infra/billing-kill-switch/README.md`. Ask before creating anything
  outside the free tier.

## Next steps (in order)

1. Days 11–12: deploy. Plan: Cloud Run (API + static web), e2-micro VM (Docker worker, free
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
