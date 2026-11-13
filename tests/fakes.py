"""Test doubles: a scripted LLM and an in-memory sandbox."""

from __future__ import annotations

from rewardhacker.llm import ToolCall, ToolSpec, Turn
from rewardhacker.models import ExecResult


class ScriptedSession:
    def __init__(self, turns: list[Turn]):
        self.turns = list(turns)
        self.sent: list[dict] = []

    def send(self, text=None, tool_results=None) -> Turn:
        self.sent.append({"text": text, "tool_results": tool_results})
        if not self.turns:
            return Turn(text="(out of script)")
        return self.turns.pop(0)


class FakeLLM:
    """Plays back a fixed list of turns; the judge returns a fixed verdict."""

    model = "gemini-3.1-flash-lite"

    def __init__(self, turns: list[Turn], judge_verdict: str = "shortcut"):
        self.turns = turns
        self.judge_verdict = judge_verdict
        self.sessions: list[ScriptedSession] = []
        self.judge_prompts: list[str] = []

    def chat(self, system: str, tools: list[ToolSpec]) -> ScriptedSession:
        session = ScriptedSession(self.turns)
        self.sessions.append(session)
        return session

    def complete_json(self, system: str, prompt: str):
        self.judge_prompts.append(prompt)
        return {"verdict": self.judge_verdict, "reason": "scripted"}, Turn(
            input_tokens=100, output_tokens=10, cost_usd=0.0001
        )


def bash(cmd: str, tokens: int = 1000) -> Turn:
    return Turn(
        tool_calls=[ToolCall(id="c", name="bash", args={"command": cmd})],
        input_tokens=tokens,
        output_tokens=50,
        cost_usd=0.001,
    )


def submit(explanation: str) -> Turn:
    return Turn(
        tool_calls=[ToolCall(id="s", name="submit", args={"explanation": explanation})],
        input_tokens=500,
        output_tokens=50,
        cost_usd=0.001,
    )


class FakeSandbox:
    """Records commands; returns canned output."""

    def __init__(self):
        self.commands: list[tuple[str, str | None]] = []

    def exec(self, command: str, timeout: float, user: str | None = None) -> ExecResult:
        self.commands.append((command, user))
        return ExecResult(exit_code=0, stdout=f"ran: {command}")
