"""The task format RewardHacker probes.

A task is a directory with a ``task.yaml`` plus the files it references::

    my-task/
      task.yaml
      environment/Dockerfile   # what the agent works in
      tests/                   # verifier files, copied in only at verification time
      solution/solve.sh        # reference solution (optional, but strongly recommended)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

TASK_FILE = "task.yaml"
NETWORK_OPT_IN = "RH_ALLOW_TASK_NETWORK"
# Real task.yaml files are a few KB. The cap keeps the (pure-Python) YAML parser from chewing
# on a huge uploaded file.
MAX_TASK_FILE_BYTES = 1024 * 1024


def task_network_allowed() -> bool:
    return os.environ.get(NETWORK_OPT_IN, "").lower() in ("1", "true", "yes")


class TaskSpecError(ValueError):
    """The task directory or its task.yaml is invalid."""


def _describe(exc: ValidationError) -> str:
    """The validation errors without the offending input values. ``str(exc)`` reprs each input
    in full before truncating it, and YAML anchors/aliases can make that repr exponentially
    large: a few hundred bytes of task.yaml would pin a CPU (and memory) for hours."""
    lines = [f"{exc.error_count()} validation error(s) for task.yaml"]
    for err in exc.errors(include_url=False, include_input=False, include_context=False):
        loc = ".".join(str(part) for part in err["loc"]) or "(root)"
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Environment(_Strict):
    dockerfile: str = "environment/Dockerfile"
    context: str = "environment"
    workdir: str = "/workspace"
    # User the agent (and the reference solution) runs as. None = the image's default user.
    # Running the agent as an unprivileged user is the main defence against tampering.
    agent_user: str | None = None
    # Network for the whole trial (agent, solution, verifier). "none" by default: the agent can't
    # exfiltrate or fetch answers. "bridge" exists for faithfully running imported benchmarks
    # whose agents normally have internet (e.g. Terminal-Bench); it's refused unless the operator
    # sets RH_ALLOW_TASK_NETWORK=1, and the web API never accepts it.
    network: Literal["none", "bridge"] = "none"


class Verifier(_Strict):
    command: str
    timeout_sec: int = Field(default=120, ge=1, le=3600)
    files: str = "tests"
    mount_path: str = "/tests"
    user: str = "root"


class Solution(_Strict):
    command: str
    timeout_sec: int = Field(default=300, ge=1, le=3600)
    files: str = "solution"
    mount_path: str = "/solution"


class Limits(_Strict):
    cpus: float = Field(default=1.0, gt=0, le=8)
    memory: str = Field(default="1g", pattern=r"^\d+[kmg]$")
    pids: int = Field(default=256, ge=16, le=4096)


class TaskSpec(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    objective: str = Field(min_length=1)
    environment: Environment = Environment()
    verifier: Verifier
    solution: Solution | None = None
    limits: Limits = Limits()

    _root: Path = PrivateAttr(default=Path("."))

    @property
    def root(self) -> Path:
        return self._root

    @classmethod
    def load(cls, path: str | Path) -> TaskSpec:
        """Load and validate a task from its directory (or its task.yaml)."""
        path = Path(path)
        root = path.parent if path.is_file() else path
        spec_file = root / TASK_FILE
        if not spec_file.is_file():
            raise TaskSpecError(f"no {TASK_FILE} found in {root}")
        if spec_file.stat().st_size > MAX_TASK_FILE_BYTES:
            raise TaskSpecError(f"{spec_file}: larger than {MAX_TASK_FILE_BYTES // 1024} KB")
        try:
            raw = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
            task = cls.model_validate(raw)
        except yaml.YAMLError as exc:
            raise TaskSpecError(f"{spec_file}: invalid YAML: {exc}") from exc
        except ValidationError as exc:
            raise TaskSpecError(f"{spec_file}: {_describe(exc)}") from exc
        task._root = root.resolve()
        task._check_files()
        return task

    def resolve(self, rel: str) -> Path:
        """Resolve a task-relative path, refusing anything that escapes the task directory."""
        target = (self._root / rel).resolve()
        if not target.is_relative_to(self._root):
            raise TaskSpecError(f"path {rel!r} escapes the task directory")
        return target

    def _check_files(self) -> None:
        if not self.resolve(self.environment.dockerfile).is_file():
            raise TaskSpecError(f"dockerfile not found: {self.environment.dockerfile}")
        if not self.resolve(self.environment.context).is_dir():
            raise TaskSpecError(f"build context not found: {self.environment.context}")
        self.resolve(self.verifier.files)  # may be absent (self-contained verifier command)
        if self.solution and not self.resolve(self.solution.files).is_dir():
            raise TaskSpecError(f"solution directory not found: {self.solution.files}")
