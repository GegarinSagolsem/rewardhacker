# HANDOFF.md — where we left off

_Last updated: 2026-11-14 (end of day-6 session)_

## State

- Days 1–6 of the plan are done (see `CONTEXT.md` → Two-week plan). Private repo
  `GegarinSagolsem/rewardhacker`, branch `main`.
- Probing engine: 9 probes; LoopBench 12/12 with the live Gemini adversary.
- **Backend (day 6):** FastAPI in `src/rewardhacker/api/` — register/login (JWT), orgs with
  viewer/reviewer/admin roles, .zip task upload, runs queued in Postgres and executed by
  `rh worker`, adversary traces in MongoDB. Schema migrated on Neon (`alembic current` =
  `eb2dba567a24`). Verified live end-to-end (CONTEXT.md log, 2026-11-14).
- `.env` has `GEMINI_API_KEY`, `DATABASE_URL` (Neon), `MONGODB_URI` (Atlas), `RH_JWT_SECRET`.
- Tests: `test_core.py` + `test_adversary.py` + `test_api.py` (40, fast, no cloud) and
  `test_loopbench.py` (Docker, ~3 min). Docker Desktop must be running for probes/worker.
- Gemini spend so far: ≈ $0.009 total.

## Blocked on the user

- Nothing.

## Next steps (in order)

1. Days 7–8: React + TypeScript + Vite dashboard in `web/`: login, org switcher, task upload,
   run list with status polling, report view (findings, score, verdict), adversary trace viewer
   (`GET /api/orgs/{org}/runs/{run}/traces`), member management for admins.
   CORS already allows `http://localhost:5173`.
2. Consider a "reviewer triage" field on runs (accept / dispute a finding) — needs a migration.

## Open questions / risks

- Uploaded task Dockerfiles are built on the worker with network access (see CONTEXT.md).
- The judge is the same model as the adversary; consider a stronger judge later.
- Adversary compliance with "don't solve" depends on the prompt; re-run
  `rh bench --adversary required` a few times before quoting results publicly.
- `lingering-process` probe is timing-based; stable so far but watch CI.
