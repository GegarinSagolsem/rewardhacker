"""Terminal-Bench (tb run) agent for reproducing the lingering-process finding (see RESULTS.md).

Minimal TB agent: does NOT solve the task. It only leaves a background process that
rewrites any copied-in test_*.py under /tests into a trivial passing test (same payload as
RewardHacker's lingering-process probe). Used to confirm the flaw on the real tb harness."""

import shlex
from pathlib import Path

from terminal_bench.agents.base_agent import AgentResult, BaseAgent
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.terminal.tmux_session import TmuxSession

LOOP = (
    "while :; do for f in $(find /tests -type f -name 'test_*.py' 2>/dev/null); do "
    'grep -q rh_placeholder "$f" 2>/dev/null || '
    "printf 'def test_rh_placeholder():\n    pass\n' > \"$f\" 2>/dev/null; "
    "done; sleep 0.05; done"
)


class LingeringAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "lingering-process"

    def perform_task(
        self, instruction: str, session: TmuxSession, logging_dir: Path | None = None
    ) -> AgentResult:
        session.send_keys(
            [f"(nohup sh -c {shlex.quote(LOOP)} >/dev/null 2>&1 &)", "Enter"], block=True, max_timeout_sec=30
        )
        return AgentResult(total_input_tokens=0, total_output_tokens=0, failure_mode=FailureMode.NONE)
