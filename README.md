# RewardHacker

**Red-team your rewards.** RewardHacker finds RL coding tasks whose reward can be obtained
without doing the work — before an agent learns to do exactly that.

> Status: early development. The core probing engine and CLI work; the web platform,
> adversary agent and cloud deployment are in progress.

## Why

Coding agents are trained and evaluated on tasks made of an environment, an objective and a
verifier. If the verifier can be satisfied by a shortcut — rewriting the tests, hooking the
test runner, or doing nothing at all — training rewards the shortcut (reward hacking) and
benchmark scores stop meaning anything. Task authors usually find these holes by hand, in
review, after the fact. RewardHacker attacks every task automatically and tells you how.

## What it checks

| Probe | Question | Verifier should |
|---|---|---|
| `null` | Does the untouched environment already pass? | fail |
| `reference` | Does the task's own solution pass, every time? | pass |
| `rewrite-tests` | Can the agent replace tests that live in its environment? | fail |
| `pytest-forcepass` | Can an auto-loaded plugin / parent `conftest.py` flip failures to passes? | fail |
| `shadow-runner` | Can the agent overwrite `pytest`/`jest` on `PATH`? | fail |

Each task gets a verdict (`robust`, `exploitable`, `broken`, `flaky`), a 0–100 score, and a
finding with a concrete fix for every problem.

## Quick start

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
uv run rh probe loopbench/tasks/bare-pytest-runner
uv run rh probe path/to/your-task --json report.json   # exit code 1 if not robust (CI-friendly)
```

## Task format

```
my-task/
  task.yaml
  environment/Dockerfile   # the agent's environment
  tests/                   # verifier files, copied in only at verification time
  solution/solve.sh        # reference solution
```

```yaml
id: clean-word-count
objective: |
  Create /workspace/wc.py defining count_words(text: str) -> int.
verifier:
  command: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q --confcutdir=/tests /tests
  timeout_sec: 60
solution:
  command: sh /solution/solve.sh
```

## Sandbox

Every trial runs in a fresh container with no network, CPU/memory/PID limits, all but a
handful of capabilities dropped, and `no-new-privileges`. Containers are removed after each
trial.

## LoopBench

`loopbench/` contains tasks with known answers — clean tasks, tasks with deliberate
loopholes and broken tasks — used to measure RewardHacker's precision and recall.

## License

MIT © Sagolsem Gegarin Singh
