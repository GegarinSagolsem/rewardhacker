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
| 6 | FastAPI backend: auth, orgs, roles, task upload, runs, job queue; traces → MongoDB | |
| 7–8 | React dashboard: reports, trace viewer, reviewer triage | |
| 9 | GCS exports (signed URLs), audit log, API keys, RAG spec check vs guidelines | |
| 10 | MCP server | |
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
