"""A small provider-neutral LLM layer with hard spending limits.

The adversary only depends on the ``LLM`` / ``ChatSession`` protocols, so tests use a scripted
fake and the provider can be swapped. ``GeminiLLM`` is the production implementation.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from .config import Settings, get_settings

# USD per 1M tokens (input, output), standard paid tier.
# Source: https://ai.google.dev/gemini-api/docs/pricing (checked 2026-11-13).
PRICES_PER_M: dict[str, tuple[float, float]] = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}


class BudgetExceeded(RuntimeError):
    """A spending limit would be exceeded; no further LLM calls are made."""


def price_for(model: str) -> tuple[float, float]:
    for prefix, price in PRICES_PER_M.items():
        if model.startswith(prefix):
            return price
    if "RH_PRICE_IN_PER_M" in os.environ and "RH_PRICE_OUT_PER_M" in os.environ:
        return float(os.environ["RH_PRICE_IN_PER_M"]), float(os.environ["RH_PRICE_OUT_PER_M"])
    raise BudgetExceeded(
        f"no price known for model {model!r}; set RH_PRICE_IN_PER_M / RH_PRICE_OUT_PER_M "
        "so spending can be capped"
    )


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = price_for(model)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000


class SpendLedger:
    """Tracks today's LLM spend in a small JSON file and refuses calls past the daily cap."""

    _lock = threading.Lock()

    def __init__(self, daily_cap_usd: float, path: Path | None = None):
        self.daily_cap_usd = daily_cap_usd
        self.path = path or Path.home() / ".rewardhacker" / "spend.json"

    def _read(self) -> dict[str, float]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def today(self) -> float:
        return self._read().get(date.today().isoformat(), 0.0)

    def check(self) -> None:
        spent = self.today()
        if spent >= self.daily_cap_usd:
            raise BudgetExceeded(
                f"daily LLM budget reached (${spent:.4f} of ${self.daily_cap_usd:.2f}); "
                "raise RH_DAILY_BUDGET_USD to continue"
            )

    def record(self, usd: float) -> None:
        with self._lock:
            data = self._read()
            key = date.today().isoformat()
            data[key] = round(data.get(key, 0.0) + usd, 6)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MongoSpendLedger(SpendLedger):
    """Daily spend shared by every process (Cloud Run instances, per-run Cloud Build workers,
    local CLI): one ``{_id: "YYYY-MM-DD" (UTC), usd}`` document per day, updated with ``$inc``.
    Fails closed: if MongoDB is unreachable, no LLM call is allowed."""

    def __init__(self, daily_cap_usd: float, uri: str, db_name: str = "rewardhacker", collection=None):
        self.daily_cap_usd = daily_cap_usd
        if collection is None:
            from pymongo import MongoClient  # optional dependency (extra: api)

            collection = MongoClient(uri, serverSelectionTimeoutMS=5000)[db_name]["llm_spend"]
        self._col = collection

    @staticmethod
    def _day() -> str:
        return datetime.now(UTC).date().isoformat()

    def today(self) -> float:
        try:
            doc = self._col.find_one({"_id": self._day()})
        except Exception as exc:
            msg = f"spend ledger unavailable ({type(exc).__name__}); refusing LLM calls"
            raise BudgetExceeded(msg) from exc
        return float(doc["usd"]) if doc else 0.0

    def record(self, usd: float) -> None:
        self._col.update_one({"_id": self._day()}, {"$inc": {"usd": usd}}, upsert=True)


def default_ledger(daily_cap_usd: float) -> SpendLedger:
    """Shared Mongo ledger when ``MONGODB_URI`` is set (and pymongo installed), else a local file."""
    uri = os.environ.get("MONGODB_URI", "").strip()
    if uri:
        try:
            return MongoSpendLedger(daily_cap_usd, uri, os.environ.get("RH_MONGODB_DB", "rewardhacker"))
        except ImportError:
            pass
    return SpendLedger(daily_cap_usd)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str | None
    name: str
    args: dict[str, Any]


@dataclass
class Turn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class ChatSession(Protocol):
    def send(
        self, text: str | None = None, tool_results: list[tuple[ToolCall, dict]] | None = None
    ) -> Turn: ...


class LLM(Protocol):
    model: str

    def chat(self, system: str, tools: list[ToolSpec]) -> ChatSession: ...

    def complete_json(self, system: str, prompt: str) -> tuple[dict, Turn]: ...


def parse_json_object(text: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


class GeminiLLM:
    """Gemini via the google-genai SDK. Every call is checked against and recorded in the ledger."""

    def __init__(self, api_key: str, model: str, ledger: SpendLedger, max_output_tokens: int = 2048):
        from google import genai  # optional dependency: pip install rewardhacker[llm]

        price_for(model)  # fail fast if we could not cap spending for this model
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.ledger = ledger
        self.max_output_tokens = max_output_tokens

    def _generate(self, contents, config):
        from google.genai import errors

        self.ledger.check()
        delay = 2.0
        for attempt in range(4):
            try:
                resp = self.client.models.generate_content(model=self.model, contents=contents, config=config)
                break
            except errors.ClientError as exc:
                if exc.code != 429 or attempt == 3:
                    raise
            except errors.ServerError:
                if attempt == 3:
                    raise
            time.sleep(delay)
            delay *= 2
        um = resp.usage_metadata
        in_tok = (um.prompt_token_count or 0) + (um.tool_use_prompt_token_count or 0) if um else 0
        out_tok = (um.candidates_token_count or 0) + (um.thoughts_token_count or 0) if um else 0
        cost = cost_usd(self.model, in_tok, out_tok)
        self.ledger.record(cost)
        return resp, Turn(input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost)

    def chat(self, system: str, tools: list[ToolSpec]) -> ChatSession:
        return _GeminiSession(self, system, tools)

    def complete_json(self, system: str, prompt: str) -> tuple[dict, Turn]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            max_output_tokens=1024,
        )
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        resp, turn = self._generate(contents, config)
        turn.text = resp.text or ""
        return parse_json_object(turn.text), turn


class _GeminiSession:
    def __init__(self, llm: GeminiLLM, system: str, tools: list[ToolSpec]):
        from google.genai import types

        self.types = types
        self.llm = llm
        self.contents: list = []
        self.config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name, description=t.description, parameters_json_schema=t.parameters
                        )
                        for t in tools
                    ]
                )
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=llm.max_output_tokens,
        )

    def send(self, text: str | None = None, tool_results: list[tuple[ToolCall, dict]] | None = None) -> Turn:
        t = self.types
        parts = [
            t.Part(function_response=t.FunctionResponse(id=call.id, name=call.name, response=result))
            for call, result in tool_results or []
        ]
        if text:
            parts.append(t.Part(text=text))
        self.contents.append(t.Content(role="user", parts=parts))
        resp, turn = self.llm._generate(self.contents, self.config)
        candidate = resp.candidates[0] if resp.candidates else None
        if candidate is None or candidate.content is None:
            return turn
        # Keep the model's own content object: it carries thought signatures Gemini needs back.
        self.contents.append(candidate.content)
        turn.text = "".join(
            p.text for p in candidate.content.parts or [] if p.text and not getattr(p, "thought", False)
        )
        turn.tool_calls = [
            ToolCall(id=fc.id, name=fc.name or "", args=dict(fc.args or {}))
            for fc in resp.function_calls or []
        ]
        return turn


def default_llm(settings: Settings | None = None) -> LLM | None:
    """The configured LLM, or None when no key is set or LLM probes are disabled."""
    s = settings or get_settings()
    if s.llm_disabled or not s.gemini_api_key:
        return None
    return GeminiLLM(s.gemini_api_key, s.model, default_ledger(s.daily_budget_usd))
