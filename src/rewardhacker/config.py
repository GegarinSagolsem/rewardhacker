"""Settings from environment variables, with an optional ``.env`` file (never committed)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(start: Path | None = None) -> Path | None:
    """Load KEY=VALUE lines from the nearest .env (cwd or a parent). Existing env vars win."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), value)
            return f
    return None


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    model: str
    daily_budget_usd: float
    run_budget_usd: float
    max_steps: int
    llm_disabled: bool


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
        model=os.environ.get("RH_MODEL", "gemini-3.1-flash-lite"),
        daily_budget_usd=_float("RH_DAILY_BUDGET_USD", 0.50),
        run_budget_usd=_float("RH_RUN_BUDGET_USD", 0.05),
        max_steps=int(_float("RH_ADVERSARY_MAX_STEPS", 15)),
        llm_disabled=os.environ.get("RH_DISABLE_LLM", "").lower() in ("1", "true", "yes"),
    )
