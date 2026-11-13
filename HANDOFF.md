# HANDOFF.md — where we left off

_Last updated: 2026-11-13 (end of day-4 session)_

## State

- Days 1–4 of the plan are built (see `CONTEXT.md` → Two-week plan). All committed to the
  private repo `GegarinSagolsem/rewardhacker`, branch `main`. CI green on GitHub Actions.
- 9 probes: 8 static + `adversary` (Gemini agent + judge).
- LoopBench: 12 tasks. 10 static tasks pass 10/10 (precision/recall 100%, stable across runs).
  2 LLM tasks (`weak-output-check`, `strong-output-check`) are **skipped until a Gemini key
  exists**; the adversary flow itself is tested end-to-end in Docker with a scripted FakeLLM.
- Tests: `tests/test_core.py` + `tests/test_adversary.py` (22, fast) and
  `tests/test_loopbench.py` (Docker, ~3 min).

## Blocked on the user

- `.env` with `GEMINI_API_KEY=...` in the repo root (template: `.env.example`). Not created yet.

## Next steps (in order)

1. When `.env` exists: verify the key without printing it; list available models and confirm
   the exact ID for `gemini-3.1-flash-lite` (update `PRICES_PER_M` / default in `config.py` if
   the ID differs).
2. Live smoke test: `uv run rh probe loopbench/tasks/weak-output-check` — expect a
   `adversary-shortcut` finding; check the cost line (should be ~$0.01–0.03).
3. `uv run rh bench --adversary required` — both LLM tasks should pass. If the adversary
   genuinely solves `weak-output-check` instead of cheating, tune `SYSTEM_PROMPT`.
4. Record live results (cost, steps, pass/fail) in `CONTEXT.md`.
5. Start day 6: FastAPI backend (see plan). Store agent traces in MongoDB.

## Open questions / risks

- The judge is the same model as the adversary; consider a stronger judge model later if
  judgements look wrong (cost trade-off).
- `lingering-process` probe is timing-based; stable in 3/3 runs so far but watch CI.
