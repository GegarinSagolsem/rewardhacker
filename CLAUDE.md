# CLAUDE.md — RewardHacker

Instructions for coding agents working in this repo. Keep this file short; details live in
the files below.

## Start of every session (read in this order, then stop reading)

1. `HANDOFF.md` — where the last session stopped and what to do next. **Read first.**
2. `CONTEXT.md` — decisions, plan, constraints, and every plan change (with dates).
3. `PRIVATE_NOTES.md` — personal notes, git-ignored; may not exist on every machine.

Do **not** read the whole codebase to orient yourself. Use the module map below and open only
the files the current task touches.

## End of every session (mandatory)

- Update `HANDOFF.md`: what was done, current state, exact next steps, open problems.
- Append any decision or plan change to `CONTEXT.md` (dated, one or two lines each).
- Commit with a descriptive message (see Git rules).

## What this is

RewardHacker red-teams RL coding tasks (Docker environment + objective + verifier + reference
solution) and reports how the reward can be obtained without doing the work.

## Module map (`src/rewardhacker/`)

| File | Responsibility |
|---|---|
| `taskspec.py` | `task.yaml` schema + loading, path-escape protection |
| `sandbox.py` | Docker CLI wrapper: image build/cache, hardened throwaway containers, `exec(user=...)` |
| `probes.py` | `Probe` base class + static probes (null, reference, 6 tamper probes) |
| `adversary.py` | LLM adversary probe: black-box agent loop (bash/submit tools) + judge |
| `llm.py` | Provider-neutral LLM protocol, `GeminiLLM`, pricing, `SpendLedger` (daily cap) |
| `config.py` | Settings from env / `.env` |
| `registry.py` | `STATIC_PROBES`, `LLM_PROBES`, `get_probes`, `llm_available` |
| `runner.py` | Runs probes → `Report` (findings, score, verdict, LLM usage) |
| `models.py` | Pydantic result types (shared with the future API) |
| `bench.py` | LoopBench runner: precision / recall against `expected.yaml` |
| `cli.py` | `rh probe`, `rh bench`, `rh validate`, `rh probes`, `rh serve`, `rh worker` |

Web backend (`src/rewardhacker/api/`, needs the `api` extra):

| File | Responsibility |
|---|---|
| `app.py` | `create_app(settings, engine, traces)` factory; routers in `routes/` (auth, orgs, tasks, runs) |
| `tables.py` | SQLAlchemy models: User, Org, Membership (role), Task, Run (= job-queue row) |
| `deps.py` | DB session, `current_user` (JWT), `require_role(Role.X)` org-scoped checks (404 for non-members) |
| `jobs.py` | Queue: `claim_next` (FOR UPDATE SKIP LOCKED), `execute`, `recover_stale`, trace split |
| `traces.py` | `MongoTraceStore` / `MemoryTraceStore` for adversary steps |
| `storage.py` | Safe zip extraction for uploads (zip-slip, symlinks, bombs) |
| `security.py`, `settings.py`, `db.py`, `schemas.py`, `worker.py` | hashing + JWT, env config, engine, I/O models, worker loop |

Web dashboard (`web/`, React 19 + TS + Vite + Tailwind v4 + TanStack Query + React Router):
`src/lib/api.ts` (typed client, JWT in localStorage), `lib/types.ts` (mirrors `api/schemas.py` +
`models.py`, keep in sync), `lib/auth.tsx`, `components/ui.tsx` (design primitives; colours are
semantic tokens in `index.css`, light + dark), `pages/` (Landing, AuthPage, Tasks, TaskDetail,
Runs, RunDetail, Members). Dev: `rh serve` on :8000 + `cd web && npm run dev` (proxies `/api`).

`migrations/` = Alembic (reads `DATABASE_URL`). After changing `tables.py`:
`uv run alembic revision --autogenerate -m "..."` then `uv run alembic upgrade head`.

`loopbench/tasks/<task>/expected.yaml` = known answer for each benchmark task.
`tests/fakes.py` = scripted `FakeLLM` + `FakeSandbox` (use these; never call a real LLM in tests).
`tests/test_api.py` runs on SQLite + `MemoryTraceStore`; never touch Neon/Atlas from tests.

## Commands

```bash
uv sync --all-extras                      # install (incl. google-genai)
uv run ruff check . && uv run ruff format .
uv run pytest tests/test_core.py tests/test_adversary.py tests/test_api.py -q   # fast, no Docker
uv run pytest tests/test_loopbench.py -q  # Docker end-to-end (~3 min)
uv run rh probe loopbench/tasks/<task> [--no-llm] [--json out.json]
uv run rh bench [--adversary off|required|all]
uv run rh serve [--reload]                # API on :8000, docs at /docs (needs DATABASE_URL, RH_JWT_SECRET)
uv run rh worker [--once]                 # executes queued runs (needs Docker)
cd web && npm run dev                     # dashboard on :5173; npm run build / npx eslint src
```

## Rules

- **Git identity:** commit as `Sagolsem Gegarin Singh <176033453+GegarinSagolsem@users.noreply.github.com>`
  (set in this repo's local config). The machine's global git identity belongs to someone
  else — never use it. End commit messages with the `Co-Authored-By: Claude ...` trailer.
- **Secrets:** API keys live only in `.env` (git-ignored). Never print, log or commit them.
  Check for a key without showing it: `awk -F= '/^GEMINI_API_KEY=/{print length($2)}' .env`.
- **LLM spend is capped and must stay capped:** total budget ≈ ₹800 (~$9). Defaults: $0.05 per
  adversary run, $0.50 per day (`SpendLedger`, `~/.rewardhacker/spend.json`). Tests use
  `FakeLLM` only. Ask before any action that could spend more than ~$0.20.
- **Cloud:** free tier only (GCP). Ask before creating anything billable.
- **Honesty:** never overstate results in README/docs. LoopBench tasks were written alongside
  the probes — say so whenever quoting its scores.
- **File encoding (Windows):** always read/write text with `encoding="utf-8"` and
  `newline="\n"`. Prefer the Edit tool over Python string-replace scripts: scripts have twice
  turned `"\n"` inside code into real line breaks and once wrote cp1252 bytes into README.md.
- Run ruff + the fast tests before every commit; run the Docker tests when touching
  `sandbox.py`, `probes.py`, `runner.py` or LoopBench tasks.
