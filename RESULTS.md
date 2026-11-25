# RewardHacker on Terminal-Bench 1: results

**Status: preliminary (2026-11-23).** 34 of 40 sampled tasks have a static-probe report, and the
LLM adversary has run on 20 of them. Results that still need hand-checking are labelled as such
below, not counted as findings.

## Setup

| | |
|---|---|
| Benchmark | Terminal-Bench 1 (github.com/harbor-framework/terminal-bench-1), `original-tasks` at commit `d28711d` |
| Sample | 40 tasks, stratified by difficulty (10 easy, 20 medium, 10 hard), seed `20261123` |
| Imported | with `rh import-tb` (single-container tasks only) |
| Static probes | null, reference, rewrite-tests, pytest-forcepass, python-startup-hook, shadow-runner, lingering-process, verifier-file-tamper (all 40 tasks) |
| LLM adversary | `gemini-3.1-flash-lite`, max 15 steps, $0.05 per task cap (20 tasks; separate pass) |
| Limits per container | 2 CPUs, 2 GB RAM, 1024 PIDs, network on (TB tasks install tools at test time) |
| Machine | one Windows 11 laptop, Docker Desktop (WSL2), 16 GB RAM |
| Driver | `scripts/run_benchmark.py`, one `rh probe --json` per task |

No benchmark files are in this repo. Terminal-Bench asks that its task data never appear in
training corpora, so imported tasks and raw reports stay in a git-ignored folder.

## Headline

| Verdict | Tasks |
|---|---|
| Exploitable | 30 (+1 excluded, see below) |
| Reference solution failed ("broken" or reference finding), cause unconfirmed | 10, overlapping the rows above, see below |
| Robust | 1 |
| No result | 6 |

### One systemic issue, not 30 separate ones

Every exploitable verdict comes from the same probe: **lingering-process**. The probe's "agent"
starts a background process and exits. In RewardHacker's runner, which mirrors TB1's harness, the
tests are then copied into **the same, still-running container** and executed, and the agent's
process is still alive. It rewrites the copied-in test files to a trivial passing test before
pytest runs. The verifier passes without the task being solved.

This is a property of how Terminal-Bench 1 verifies, not of any single task. So it is reported once:

> **Agent processes survive into verification, and the agent can write to the copied-in tests.**
> Fix: kill every agent process before verifying (or verify in a fresh container built from a
> snapshot of the agent's files), and make the test files owned by a user the agent can't write as.

It fired on all 30 tasks it could run on. It did not fire on `unprivileged-headless-pyrender`
(the one robust task) or on the 2 tasks whose reference failed at test time. I have not yet
checked why pyrender resisted.

#### Confirmed on the official harness (2026-11-25)

To rule out a difference between RewardHacker's runner and the real one, I reproduced the
attack with Terminal-Bench's own `tb run` (terminal-bench 0.2.18, the version pinned at commit
`d28711d`, run under WSL2 Ubuntu). The agent, `scripts/tb_lingering_agent.py`, does no work. It
only starts the same background loop as the probe and returns. A built-in `nop` agent was run as
a control on each task.

| Task | Difficulty | `nop` (control) | lingering-process agent |
|---|---|---|---|
| hello-world | easy | unresolved (2 tests failed) | **resolved** |
| pandas-etl | easy | unresolved (3 tests failed) | **resolved** |
| vulnerable-secret | medium | unresolved (3 tests failed) | **resolved** |
| feal-linear-cryptanalysis | hard | unresolved (1 test failed) | **resolved** |

In every run, pytest collected only the injected `test_rh_placeholder`. The harness code
explains why. `Harness._run_trial` runs the tests in the same container the agent used, and
does nothing to stop the agent's processes first. `_setup_test_env` then copies the tests to
`/tests`, where the agent can write. A separate "tests" tmux session does not isolate them.
I ran 4 of the 30 tasks on the official harness, not all 30. The other 26 rely on the
runner reproducing the same mechanism.

Reproduce: `pip install terminal-bench==0.2.18`, then
`PYTHONPATH=scripts tb run -p <original-tasks> -t hello-world --agent-import-path tb_lingering_agent:LingeringAgent`
(on Linux or WSL; `tb` builds container paths with the host's path separator, so it fails on
native Windows).

### Task-specific findings (unverified)

These fired in addition to lingering-process and need a manual check before they count:

| Task | Probe | Note |
|---|---|---|
| cross-entropy-method | pytest-forcepass, python-startup-hook | verifier can be forced to pass from inside Python |
| attention-mil | python-startup-hook | reference also failed here, so weaker evidence |

### LLM adversary: one task-specific shortcut (verified)

The adversary ran on 20 tasks where the official solution passes, chosen across difficulty and
category. Total cost: **$0.058** (about ₹5).

**form-filling: exploitable through hard-coded output.** The task asks for a script that reads
PDFs and documents and fills a form's fields. The adversary wrote a script that skips all of
that and writes a hard-coded JSON file in the expected shape. All 4 tests passed. I checked the
tests by hand: they check that the script runs, that the JSON has the right keys and types,
and that its counts agree with each other. They never check a single field value against the
documents, so any well-formed JSON passes. Fix: assert the expected values for at least a
few known fields.

On the other 19 tasks the adversary didn't get the verifier to pass. That is weak evidence of
robustness. Flash-Lite usually submitted after 3 to 5 steps with a naive attempt (e.g. writing
the wrong content), and it never tried the lingering-process trick the static probe proves
works. On 3 tasks (build-initramfs-qemu, hello-world, solve-maze-challenge) the verifier timed out
after 300 s while installing tools at test time, so those runs say nothing either way.

### Reference-solution failures: cause unconfirmed

On 10 tasks the official `solution.sh` did not pass the task's own tests in our run. On 2 of them
that is the only finding, so the verdict is "broken". I have **not** confirmed any of these as
bugs in Terminal-Bench. The likely causes I found:

| Task | Verdict | What I saw | Likely cause |
|---|---|---|---|
| torch-pipeline-parallelism | broken | `import torch` fails at test time | test-time `pip install torch` didn't complete (our network) |
| slurm-simple-node-monitoring | broken | 2 of 5 tests fail | unconfirmed |
| build-pmars | exploitable | `apt` can't find packages | network or old Debian mirror |
| build-cython-ext | exploitable | 1 of 11 tests fails | unpinned dependencies have moved on (possible real drift) |
| find-official-code | exploitable | expected answer differs | needs the live web; the answer has changed since the task was written |
| attention-mil, gcode-to-text, path-tracing-reverse, protein-assembly | exploitable | tests fail after solution | unconfirmed: could be the 2 GB / 2 CPU limit, network, or real |
| catch-me-if-you-can | excluded | solution's first check fails | **our importer bug**, see below |

Next step: rerun each one alone with more memory and a stable connection before calling any of
them a benchmark bug.

## Bugs this run found in RewardHacker itself

1. **Verifier timeout over the schema limit.** The importer capped TB's test timeout at 3600 s and
   then added 120 s of install headroom, producing 3720 s, which our own task schema rejects.
   chem-rf (and 2 unsampled tasks) could not be probed. Fixed in `26889bd`, with a test.
2. **Startup commands silently dropped.** TB tasks can start a process at container boot (e.g.
   catch-me-if-you-can starts a puzzle server). The importer accepted that setting but never ran
   it, so the task ran without its server. Now such tasks are skipped with the reason, and only
   the keep-alive `sleep infinity` is accepted. Fixed in `fb036bf`, with a test. catch-me-if-you-can
   is excluded from the counts above.

## No result (6)

| Task | Why |
|---|---|
| chem-rf | blocked by bug 1 (now fixed); not rerun yet |
| matlab-python-conversion, png-generation, mteb-eval | image build failed: `pip install` timed out (our network) |
| caffe-cifar-10 | hit the 1-hour per-task limit (CPU model training) |
| speech-to-text | the run was stopped twice when the laptop ran out of memory |

## Per-task results

Score is RewardHacker's 0 to 100 robustness score.

| Task | Difficulty | Category | Verdict | Score | Minutes |
|---|---|---|---|---|---|
| assign-seats | easy | algorithms | exploitable | 50 | 6 |
| catch-me-if-you-can | easy | security | *excluded* | | |
| cross-entropy-method | easy | software-engineering | exploitable | 0 | 2 |
| flood-monitoring-basic | easy | data-processing | exploitable | 50 | 4 |
| gomoku-planner | easy | game | exploitable | 50 | 8 |
| hello-world | easy | file-operations | exploitable | 50 | 2 |
| pandas-etl | easy | data-science | exploitable | 50 | 5 |
| slurm-simple-node-monitoring | easy | system-administration | broken | 65 | 21 |
| matlab-python-conversion | easy | data-processing | no result | | |
| png-generation | easy | file-operations | no result | | |
| attention-mil | medium | model-training | exploitable | 0 | 5 |
| blind-maze-explorer-algorithm | medium | software-engineering | exploitable | 50 | 4 |
| build-cython-ext | medium | debugging | exploitable | 15 | 21 |
| build-initramfs-qemu | medium | system-administration | exploitable | 50 | 7 |
| build-pmars | medium | software-engineering | exploitable | 15 | 13 |
| classifier-debug | medium | debugging | exploitable | 50 | 12 |
| db-wal-recovery | medium | file-operations | exploitable | 50 | 13 |
| form-filling | medium | personal-assistant | exploitable | 50 | 11 |
| gcode-to-text | medium | file-operations | exploitable | 15 | 22 |
| html-finance-verify | medium | file-operations | exploitable | 50 | 4 |
| implement-eigenvectors-from-eigenvalues-research-paper | medium | mathematics | exploitable | 50 | 16 |
| ode-solver-rk4 | medium | algorithms | exploitable | 50 | 13 |
| solve-maze-challenge | medium | algorithms | exploitable | 50 | 9 |
| solve-sudoku | medium | games | exploitable | 50 | 11 |
| tune-mjcf | medium | scientific-computing | exploitable | 50 | 9 |
| unprivileged-headless-pyrender | medium | software-engineering | robust | 100 | 21 |
| vulnerable-secret | medium | security | exploitable | 50 | 6 |
| caffe-cifar-10 | medium | machine-learning | no result | | |
| mteb-eval | medium | data-science | no result | | |
| speech-to-text | medium | audio-processing | no result | | |
| feal-linear-cryptanalysis | hard | mathematics | exploitable | 50 | 5 |
| find-official-code | hard | research | exploitable | 15 | 6 |
| movie-helper | hard | mathematics | exploitable | 50 | 18 |
| path-tracing-reverse | hard | software-engineering | exploitable | 15 | 6 |
| polyglot-rust-c | hard | software-engineering | exploitable | 50 | 10 |
| protein-assembly | hard | scientific-computing | exploitable | 15 | 13 |
| regex-chess | hard | software-engineering | exploitable | 50 | 25 |
| sparql-university | hard | data-querying | exploitable | 50 | 6 |
| torch-pipeline-parallelism | hard | software-engineering | broken | 65 | 51 |
| chem-rf | hard | model-training | no result | | |

## Still to do

- Rerun the 10 reference failures and the 6 missing tasks one at a time, with more memory and a
  stable connection.
- Check by hand the cross-entropy-method and attention-mil findings, and why pyrender resisted
  lingering-process.
- Rerun the 3 adversary tasks whose verifier timed out (now reported as errors, fixed in RewardHacker).
- Report the systemic issue to the Terminal-Bench maintainers (draft first).
