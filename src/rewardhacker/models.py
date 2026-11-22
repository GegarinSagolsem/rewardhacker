"""Result types shared by the probes, the CLI and (later) the API."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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


class LLMUsage(BaseModel):
    model: str = ""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd = round(self.cost_usd + cost_usd, 6)

    def merge(self, other: LLMUsage) -> None:
        self.model = self.model or other.model
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd = round(self.cost_usd + other.cost_usd, 6)


class AgentStep(BaseModel):
    step: int
    text: str = ""  # anything the model said besides tool calls
    tool: str | None = None
    args: dict = {}
    output: str = ""


AgentStopReason = Literal["submitted", "max_steps", "budget", "no_tool_call", "error"]


class AgentRun(BaseModel):
    steps: list[AgentStep] = []
    explanation: str | None = None  # the agent's own description of its exploit
    stop_reason: AgentStopReason = "max_steps"
    error: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    judgement: Literal["shortcut", "genuine", "unknown"] | None = None
    judge_reason: str | None = None


class Trial(BaseModel):
    index: int
    setup: ExecResult | None = None
    verify: ExecResult | None = None
    passed: bool | None = None  # None = skipped / errored
    note: str | None = None
    agent: AgentRun | None = None


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
    llm_usage: LLMUsage | None = None


def score_findings(findings: list[Finding]) -> int:
    return max(0, 100 - sum(SEVERITY_PENALTY[f.severity] for f in findings))


def verdict_for(findings: list[Finding], probes: list[ProbeResult]) -> Verdict:
    if any(f.severity == Severity.CRITICAL for f in findings):
        return "exploitable"
    if any(f.severity == Severity.HIGH for f in findings):
        return "broken"
    if any(f.severity == Severity.MEDIUM for f in findings):
        return "flaky"
    # "Robust" is a claim about every probe; one that errored leaves the question open.
    if any(p.status == "error" for p in probes) or not any(p.status in ("ok", "finding") for p in probes):
        return "inconclusive"
    return "robust"
