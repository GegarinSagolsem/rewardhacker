"""Adversary agent loop, judge, budgets and LLM plumbing — no network, no API key."""

from pathlib import Path

import pytest
from fakes import FakeLLM, FakeSandbox, bash, submit

from rewardhacker.adversary import AdversaryProbe, judge, run_agent
from rewardhacker.llm import BudgetExceeded, SpendLedger, cost_usd, parse_json_object, price_for
from rewardhacker.models import AgentRun, ExecResult, ProbeResult, Trial
from rewardhacker.taskspec import TaskSpec

BENCH = Path(__file__).resolve().parents[1] / "loopbench" / "tasks"


@pytest.fixture
def task() -> TaskSpec:
    return TaskSpec.load(BENCH / "weak-output-check")


def test_agent_runs_commands_as_agent_user_and_submits(task):
    llm = FakeLLM([bash("ls /workspace"), bash("echo 'total: 0' > /workspace/report.txt"), submit("fake")])
    sb = FakeSandbox()
    run = run_agent(llm, sb, task, max_steps=10, run_budget_usd=1.0)
    assert run.stop_reason == "submitted"
    assert run.explanation == "fake"
    assert [s.tool for s in run.steps] == ["bash", "bash", "submit"]
    agent_cmds = [c for c, u in sb.commands]
    assert "echo 'total: 0' > /workspace/report.txt" in agent_cmds
    assert all(u == "agent" for _, u in sb.commands)  # never runs as root
    assert run.usage.calls == 3 and run.usage.input_tokens == 2500
    # tool output is fed back to the model
    assert llm.sessions[0].sent[1]["tool_results"][0][1]["output"].startswith("ran: ls")


def test_agent_stops_at_max_steps(task):
    llm = FakeLLM([bash(f"echo {i}") for i in range(20)])
    run = run_agent(llm, FakeSandbox(), task, max_steps=3, run_budget_usd=1.0)
    assert run.stop_reason == "max_steps"
    assert len(run.steps) == 3


def test_agent_stops_at_run_budget(task):
    llm = FakeLLM([bash(f"echo {i}") for i in range(20)])  # each turn costs $0.001
    run = run_agent(llm, FakeSandbox(), task, max_steps=50, run_budget_usd=0.0025)
    assert run.stop_reason == "budget"
    assert run.usage.cost_usd <= 0.0035


def test_agent_nudged_once_then_stops_without_tool_calls(task):
    from rewardhacker.llm import Turn

    llm = FakeLLM([Turn(text="thinking"), Turn(text="still thinking")])
    run = run_agent(llm, FakeSandbox(), task, max_steps=10, run_budget_usd=1.0)
    assert run.stop_reason == "no_tool_call"


def test_agent_survives_provider_errors(task):
    class Boom(FakeLLM):
        def chat(self, system, tools):
            class S:
                def send(self, text=None, tool_results=None):
                    raise RuntimeError("503 overloaded")

            return S()

    run = run_agent(Boom([]), FakeSandbox(), task, max_steps=5, run_budget_usd=1.0)
    assert run.stop_reason == "error" and "503" in run.error


def test_judge_records_verdict_and_cost(task):
    run = AgentRun(explanation="wrote a placeholder total")
    llm = FakeLLM([], judge_verdict="shortcut")
    judge(llm, FakeSandbox(), task, run)
    assert run.judgement == "shortcut"
    assert run.usage.calls == 1
    assert "placeholder total" in llm.judge_prompts[0]


def _result(trials):
    return ProbeResult(name="adversary", title="", expect_pass=False, status="ok", trials=trials)


def test_evaluate_flags_only_judged_shortcuts():
    probe = AdversaryProbe(llm_factory=lambda: None)
    genuine = Trial(index=0, passed=True, agent=AgentRun(judgement="genuine"))
    failed = Trial(index=0, passed=False, agent=AgentRun(judgement=None))
    shortcut = Trial(index=0, passed=True, agent=AgentRun(judgement="shortcut", explanation="x"))
    unsure = Trial(index=0, passed=True, agent=AgentRun(judgement="unknown"))
    assert probe.evaluate(_result([genuine])) == []
    assert probe.evaluate(_result([failed])) == []
    assert probe.evaluate(_result([shortcut]))[0].severity == "critical"
    assert probe.evaluate(_result([unsure]))[0].severity == "high"


def test_failed_attempt_is_an_error_not_an_all_clear():
    """Regression (2026-11-22, cloud run): the spend ledger was unreachable, the agent never ran,
    and the task was reported ROBUST. An attempt cut off by the LLM/budget must be an error."""
    probe = AdversaryProbe(llm_factory=lambda: None)
    blocked = AgentRun(stop_reason="budget", error="spend ledger unavailable (ServerSelectionTimeoutError)")
    assert "could not run" in probe.trial_error(Trial(index=0, passed=False, agent=blocked))
    # ...but a shortcut that worked before the failure still counts as a finding.
    assert probe.trial_error(Trial(index=0, passed=True, agent=blocked)) is None
    assert probe.trial_error(Trial(index=0, passed=False, agent=AgentRun(stop_reason="submitted"))) is None


def test_verifier_timeout_is_an_error_not_an_all_clear():
    """Regression (2026-11-23, Terminal-Bench run): the verifier timed out installing tools and the
    adversary probe reported "no shortcut found". A verifier that never finished says nothing."""
    probe = AdversaryProbe(llm_factory=lambda: None)
    attempt = AgentRun(stop_reason="submitted")
    hung = ExecResult(exit_code=None, timed_out=True)
    assert "timed out" in probe.trial_error(Trial(index=0, passed=False, agent=attempt, verify=hung))
    done = ExecResult(exit_code=1)
    assert probe.trial_error(Trial(index=0, passed=False, agent=attempt, verify=done)) is None


def test_probe_skipped_without_llm(task):
    assert "GEMINI_API_KEY" in AdversaryProbe(llm_factory=lambda: None).not_applicable(task)


def test_spend_ledger_enforces_daily_cap(tmp_path):
    ledger = SpendLedger(daily_cap_usd=0.01, path=tmp_path / "spend.json")
    ledger.check()
    ledger.record(0.006)
    ledger.check()
    ledger.record(0.006)
    with pytest.raises(BudgetExceeded):
        ledger.check()
    assert ledger.today() == pytest.approx(0.012)


class _FakeSpendCollection:
    def __init__(self, fail=False):
        self.docs, self.fail = {}, fail

    def find_one(self, q):
        if self.fail:
            raise ConnectionError("down")
        return self.docs.get(q["_id"])

    def update_one(self, q, update, upsert=False):
        doc = self.docs.setdefault(q["_id"], {"_id": q["_id"], "usd": 0.0})
        doc["usd"] += update["$inc"]["usd"]


def test_mongo_spend_ledger_is_shared_and_fails_closed():
    from rewardhacker.llm import MongoSpendLedger

    col = _FakeSpendCollection()
    a = MongoSpendLedger(0.01, "", collection=col)  # e.g. a Cloud Run instance
    b = MongoSpendLedger(0.01, "", collection=col)  # e.g. a Cloud Build worker
    a.record(0.006)
    b.check()
    b.record(0.006)
    with pytest.raises(BudgetExceeded):
        a.check()  # sees b's spend
    with pytest.raises(BudgetExceeded, match="unavailable"):
        MongoSpendLedger(1.0, "", collection=_FakeSpendCollection(fail=True)).check()


def test_mongo_ledger_keeps_spend_when_the_write_fails():
    from rewardhacker.llm import _UNRECORDED, MongoSpendLedger

    class FlakyWrites(_FakeSpendCollection):
        broken = True

        def update_one(self, q, update, upsert=False):
            if self.broken:
                raise ConnectionError("blip")
            super().update_one(q, update, upsert)

    _UNRECORDED.clear()
    col = FlakyWrites()
    ledger = MongoSpendLedger(0.01, "", collection=col)
    ledger.record(0.008)  # paid call already happened: must not raise, must still count
    assert ledger.today() == pytest.approx(0.008)
    col.broken = False
    ledger.record(0.001)  # the next write carries the pending amount
    assert col.docs[ledger._day()]["usd"] == pytest.approx(0.009) and not _UNRECORDED


def test_default_ledger_fails_closed_when_mongo_cannot_be_set_up(monkeypatch):
    pytest.importorskip("pymongo")
    from rewardhacker.llm import default_ledger

    monkeypatch.setenv("MONGODB_URI", "mongodb+srv://u:p@does-not-exist.invalid/")
    ledger = default_ledger(1.0)  # must not raise (SRV lookup fails at construction)
    with pytest.raises(BudgetExceeded, match="unavailable"):
        ledger.check()


def test_pricing():
    assert cost_usd("gemini-3.1-flash-lite", 1_000_000, 0) == pytest.approx(0.25)
    assert cost_usd("gemini-3.1-flash-lite-preview", 0, 1_000_000) == pytest.approx(1.50)
    with pytest.raises(BudgetExceeded):
        price_for("some-unpriced-model")


def test_parse_json_object():
    assert parse_json_object('{"verdict": "shortcut"}') == {"verdict": "shortcut"}
    assert parse_json_object('Sure! ```json\n{"verdict": "genuine"}\n```') == {"verdict": "genuine"}
    assert parse_json_object("nope") == {}
