# HANDOFF.md — where we left off

_Last updated: 2026-11-14 (days 4–5 closed with live Gemini; day 6 not started)_

## State

- Days 1–5 of the plan are done (see `CONTEXT.md` → Two-week plan). Private repo
  `GegarinSagolsem/rewardhacker`, branch `main`.
- 9 probes: 8 static + `adversary` (Gemini agent + judge).
- LoopBench: 12 tasks, **12/12 with the live adversary** (`rh bench --adversary required`,
  2026-11-14). Adversary prompt was tuned after the first live run (see CONTEXT.md log).
- Gemini spend so far: $0.0072 total.
- `.env` exists with `GEMINI_API_KEY`, `DATABASE_URL` (Neon, verified connecting) and
  `MONGODB_URI` (Atlas). Check values without printing them (see CLAUDE.md).
- Tests: `tests/test_core.py` + `tests/test_adversary.py` (22, fast) and
  `tests/test_loopbench.py` (Docker, ~3 min). Docker Desktop must be running.

## Blocked on the user

- Nothing. All three services verified connecting on 2026-11-14 (Mongo server 8.0.37).
  If Atlas times out later, the user's IP probably changed → Atlas Network Access.

## Next steps (in order)

1. Day 6: FastAPI backend — auth (JWT + hashed passwords), orgs + roles, task upload, runs,
   Postgres-backed job queue (`SELECT … FOR UPDATE SKIP LOCKED`) + worker process that calls
   `runner.py`; SQLAlchemy + Alembic on Neon; agent traces → MongoDB.
2. Keep tests DB-free where possible (SQLite / mongomock or fakes); don't hit Neon/Atlas in CI.

## Open questions / risks

- The judge is the same model as the adversary; consider a stronger judge model later if
  judgements look wrong (cost trade-off).
- Adversary compliance with "don't solve" depends on the prompt; one live run each so far.
  Re-run `rh bench --adversary required` a few times before quoting results publicly.
- `lingering-process` probe is timing-based; stable so far but watch CI.
