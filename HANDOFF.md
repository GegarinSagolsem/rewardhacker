# HANDOFF.md — where we left off

_Last updated: 2026-11-14 (end of days 7–8 session)_

## State

- Days 1–8 of the plan are done (see `CONTEXT.md` → Two-week plan). Private repo
  `GegarinSagolsem/rewardhacker`, branch `main`.
- Probing engine: 9 probes; LoopBench 12/12 with the live Gemini adversary.
- Backend: FastAPI in `src/rewardhacker/api/` (auth, org roles, uploads, Postgres job queue,
  Mongo traces). Neon schema at Alembic `eb2dba567a24`.
- **Dashboard (days 7–8):** `web/` — landing page, sign in/up, org switcher, tasks (drag-and-drop
  upload, latest verdict per task), task detail (start run, optional LLM adversary), runs list
  (status filters, live polling), run report (verdict, score, findings + fixes, adversary
  replay, probe table), members (admin role management). Light/dark. Checked with Playwright
  screenshots (desktop + mobile, both themes).
- Tests: Python 40 fast + Docker LoopBench; web: eslint + `tsc -b` + `vite build` (CI job `web`).
- Gemini spend so far: ≈ $0.011 total.

## Blocked on the user

- Nothing.

## Next steps (in order)

1. Day 9: report exports to GCS (signed URLs; local-disk fallback until GCP exists), audit log
   table (who uploaded / started / changed roles), org API keys for CI use, RAG check of task
   specs against written guidelines (Mongo Atlas vector search).
2. Small UI follow-ups: reviewer triage on findings (accept / dispute, needs a migration);
   move `verdictTone`/`atLeast` out of component files (4 react-refresh lint warnings).

## Open questions / risks

- Uploaded task Dockerfiles are built on the worker with network access (see CONTEXT.md).
- The judge is the same model as the adversary; consider a stronger judge later.
- Adversary compliance with "don't solve" depends on the prompt; re-run
  `rh bench --adversary required` a few times before quoting results publicly.
- `lingering-process` probe is timing-based; stable so far but watch CI.
