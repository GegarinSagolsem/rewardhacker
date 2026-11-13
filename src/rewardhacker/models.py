"""Result types shared by the probes, the CLI and (later) the API."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class Severity(StrEnum):
    CRITICAL = "critical"  # the reward can be obtained without doing the task
    HIGH = "high"  # the task cannot be solved / the verifier rejects the reference
    MEDIUM = "medium"  # the reward is noisy
    LOW = "low"
    INFO = "info"


SEVERITY_PENALTY = {
    Severity.CRITICAL: 50,
    Severity.HIGH: 35,
    Severity.MEDIUM: 15,
    Severity.LOW: 5,
    Severity.INFO: 0,
}


class ExecResult(BaseModel):
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_sec: float = 0.0


class Trial(BaseModel):
    index: int
    setup: ExecResult | None = None
    verify: ExecResult | None = None
    passed: bool | None = None  # None = skipped / errored
    note: str | None = None


class Finding(BaseModel):
    code: str
    severity: Severity
    probe: str
    title: str
    detail: str
    recommendation: str = ""


ProbeStatus = Literal["ok", "finding", "skipped", "error"]


class ProbeResult(BaseModel):
    name: str
    title: str
    expect_pass: bool
    status: ProbeStatus
    trials: list[Trial] = []
    note: str | None = None

    @property
    def ran(self) -> list[Trial]:
        return [t for t in self.trials if t.passed is not None]

    @property
    def pass_count(self) -> int:
        return sum(1 for t in self.ran if t.passed)


Verdict = Literal["robust", "exploitable", "broken", "flaky", "inconclusive"]


class Report(BaseModel):
    task_id: str
    image: str
    rewardhacker_version: str
    started_at: str
    duration_sec: float
    probes: list[ProbeResult]
    findings: list[Finding]
    score: int
    verdict: Verdict


def score_findings(findings: list[Finding]) -> int:
    return max(0, 100 - sum(SEVERITY_PENALTY[f.severity] for f in findings))


def verdict_for(findings: list[Finding], probes: list[ProbeResult]) -> Verdict:
    if any(f.severity == Severity.CRITICAL for f in findings):
        return "exploitable"
    if any(f.severity == Severity.HIGH for f in findings):
        return "broken"
    if any(f.severity == Severity.MEDIUM for f in findings):
        return "flaky"
    if not any(p.status in ("ok", "finding") for p in probes):
        return "inconclusive"
    return "robust"
