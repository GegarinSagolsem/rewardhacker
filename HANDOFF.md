# HANDOFF.md — where we left off

_Last updated: 2026-11-14 (end of day-9 session)_

## State

- Days 1–9 of the plan are done (see `CONTEXT.md` → Two-week plan). Private repo
  `GegarinSagolsem/rewardhacker`, branch `main`.
- Probing engine: 9 probes; LoopBench 12/12 with the live Gemini adversary.
- Backend: FastAPI (auth, org roles, uploads, Postgres job queue, Mongo traces) plus day 9:
  audit log, org API keys (`rh_…`), exports (runs CSV/JSONL, report MD/JSON; local HMAC links,
  GCS signed URLs when `RH_GCS_BUCKET` is set), guidelines + RAG spec check (Gemini embeddings,
  Atlas Vector Search index `guideline_vectors`, READY). Neon schema at Alembic `81fb72ee86e3`.
- Dashboard: adds Guidelines, API keys, Activity pages, report download / runs export menus,
  and a guideline-check panel on the task page. Checked with Playwright (desktop + mobile, both
  themes) and a real browser download test.
- Tests: 50 fast Python tests (`test_core`, `test_adversary`, `test_api`, `test_api_data`) +
  Docker LoopBench; web eslint + tsc + build in CI.
- Gemini spend so far: ≈ $0.013 total.

## Blocked on the user

- Nothing.

## Next steps (in order)

1. Day 10: MCP server exposing RewardHacker to AI tools (list tasks, start run, get report,
   run spec check), authenticated with an org API key.
2. Days 11–12: GCP deploy. Verify the GCS export path for real (needs a service account that
   can sign URLs) and open Atlas network access for Cloud Run.
3. Small follow-ups: reviewer triage on findings; the 4 react-refresh lint warnings.

## Open questions / risks

- Uploaded task Dockerfiles are built on the worker with network access (see CONTEXT.md).
- Spec-check quality depends on the guidelines and one Flash-Lite call; it can over-report.
  The UI shows the cited guideline section so a human can judge each issue.
- The judge is the same model as the adversary; consider a stronger judge later.
- `lingering-process` probe is timing-based; stable so far but watch CI.
