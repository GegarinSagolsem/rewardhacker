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
| `python-startup-hook` | Can a `.pth` file force every Python process to exit 0? | fail |
| `shadow-runner` | Can the agent overwrite `pytest`/`jest` on `PATH`? | fail |
| `lingering-process` | Can a background process rewrite tests after they are copied in? | fail |
| `verifier-file-tamper` | Can the agent edit a script the verifier command runs? | fail |

All probe actions run as the task's `agent_user`, i.e. with the same privileges a real agent
would have.

### The most important finding so far

If the agent runs as **root**, no verifier inside the same container can be trusted — not
even one that follows the usual advice (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `--confcutdir`,
`python -m pytest`, tests copied in at verification time). A `.pth` startup hook defeats
`python -I`, and a lingering background process can rewrite tests after they arrive.
LoopBench's `root-agent-textbook` task demonstrates both. Running the agent as an
unprivileged `agent_user` and the verifier as root closes these holes
(`hardened-word-count`).

Each task gets a verdict (`robust`, `exploitable`, `broken`, `flaky`), a 0–100 score, and a
finding with a concrete fix for every problem.

## Quick start

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync --all-extras          # --all-extras adds the Gemini SDK for the adversary probe
uv run rh probe loopbench/tasks/bare-pytest-runner
uv run rh probe path/to/your-task --json report.json   # exit code 1 if not robust (CI-friendly)
uv run rh bench                                        # run LoopBench, report precision/recall
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

`loopbench/tasks/` holds 10 tasks with known answers: hardened tasks with exactly one
deliberate flaw each, two "naive" root-agent tasks, and clean tasks (including decoys) that
must **not** be flagged. `rh bench` probes them all and reports precision and recall.

Current result: 10/10 tasks correct, precision 100%, recall 100% (stable across repeated
runs). Caveat: these tasks were written alongside the probes, so this measures that each
probe works as designed — not how well RewardHacker finds problems nobody anticipated. That
is what the LLM adversary probe and runs on public benchmarks are for.

## License

MIT © Sagolsem Gegarin Singh
