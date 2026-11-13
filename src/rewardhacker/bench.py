"""LoopBench: measure RewardHacker against tasks whose problems are known in advance.

Each benchmark task directory has an ``expected.yaml``::

    verdict: exploitable            # robust | exploitable | broken | flaky
    findings: [tests-rewritable]    # finding codes that must be reported (and no others)
    trials: {reference: 8}          # optional per-probe trial overrides
    requires: [adversary]           # optional: probes the task needs (skipped if unavailable)

Scoring is per finding code: a reported code that is expected is a true positive, a
reported code that is not expected is a false positive, an expected code that is missing is
a false negative.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from pydantic import BaseModel

from .models import Report
from .registry import LLM_PROBES, STATIC_PROBES, llm_available
from .runner import probe_task
from .taskspec import TaskSpec

EXPECTED_FILE = "expected.yaml"


class Expected(BaseModel):
    verdict: str
    findings: list[str] = []
    trials: dict[str, int] | None = None
    requires: list[str] = []


class TaskOutcome(BaseModel):
    task_id: str
    expected: Expected
    report: Report | None = None
    error: str | None = None
    skipped: str | None = None

    @property
    def found(self) -> set[str]:
        return {f.code for f in self.report.findings} if self.report else set()

    @property
    def true_positives(self) -> set[str]:
        return self.found & set(self.expected.findings)

    @property
    def false_positives(self) -> set[str]:
        return self.found - set(self.expected.findings)

    @property
    def false_negatives(self) -> set[str]:
        return set(self.expected.findings) - self.found

    @property
    def verdict_ok(self) -> bool:
        return self.report is not None and self.report.verdict == self.expected.verdict

    @property
    def correct(self) -> bool:
        return self.verdict_ok and not self.false_positives and not self.false_negatives


class BenchResult(BaseModel):
    all_outcomes: list[TaskOutcome]

    @property
    def outcomes(self) -> list[TaskOutcome]:
        """Outcomes that count towards the metrics (skipped tasks excluded)."""
        return [o for o in self.all_outcomes if not o.skipped]

    @property
    def skipped(self) -> list[TaskOutcome]:
        return [o for o in self.all_outcomes if o.skipped]

    def _count(self, attr: str) -> int:
        return sum(len(getattr(o, attr)) for o in self.outcomes)

    @property
    def precision(self) -> float:
        tp, fp = self._count("true_positives"), self._count("false_positives")
        return tp / (tp + fp) if tp + fp else 1.0

    @property
    def recall(self) -> float:
        tp, fn = self._count("true_positives"), self._count("false_negatives")
        return tp / (tp + fn) if tp + fn else 1.0

    @property
    def verdict_accuracy(self) -> float:
        return sum(o.verdict_ok for o in self.outcomes) / len(self.outcomes) if self.outcomes else 0.0

    def summary(self) -> dict:
        return {
            "tasks": len(self.outcomes),
            "tasks_skipped": len(self.skipped),
            "tasks_fully_correct": sum(o.correct for o in self.outcomes),
            "verdict_accuracy": round(self.verdict_accuracy, 3),
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "true_positives": self._count("true_positives"),
            "false_positives": self._count("false_positives"),
            "false_negatives": self._count("false_negatives"),
        }


def discover(bench_dir: Path) -> list[Path]:
    return sorted(d for d in bench_dir.iterdir() if (d / EXPECTED_FILE).is_file())


def load_expected(task_dir: Path) -> Expected:
    return Expected.model_validate(yaml.safe_load((task_dir / EXPECTED_FILE).read_text(encoding="utf-8")))


def run_one(task_dir: Path, adversary: str = "required") -> TaskOutcome:
    """Probe one benchmark task. ``adversary``: "off", "required" (only tasks that need it) or "all"."""
    expected = load_expected(task_dir)
    llm_names = {p.name for p in LLM_PROBES}
    needs_llm = bool(llm_names & set(expected.requires))
    available = llm_available()
    if needs_llm and (adversary == "off" or not available):
        reason = "adversary disabled" if adversary == "off" else "no LLM configured"
        return TaskOutcome(task_id=task_dir.name, expected=expected, skipped=f"needs LLM probe ({reason})")
    use_llm = available and (adversary == "all" or (adversary == "required" and needs_llm))
    names = [p.name for p in STATIC_PROBES] + ([p.name for p in LLM_PROBES] if use_llm else [])
    try:
        task = TaskSpec.load(task_dir)
        report = probe_task(task, probe_names=names, trials=expected.trials)
        return TaskOutcome(task_id=task.id, expected=expected, report=report)
    except Exception as exc:  # one broken task should not sink the whole benchmark
        return TaskOutcome(task_id=task_dir.name, expected=expected, error=f"{type(exc).__name__}: {exc}")


def run_bench(bench_dir: Path, jobs: int = 4, adversary: str = "required", on_done=None) -> BenchResult:
    dirs = discover(bench_dir)
    outcomes: list[TaskOutcome] = []
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for outcome in pool.map(lambda d: run_one(d, adversary), dirs):
            outcomes.append(outcome)
            if on_done:
                on_done(outcome)
    return BenchResult(all_outcomes=outcomes)
