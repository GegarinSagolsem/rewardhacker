"""The task format RewardHacker probes.

A task is a directory with a ``task.yaml`` plus the files it references::

    my-task/
      task.yaml
      environment/Dockerfile   # what the agent works in
      tests/                   # verifier files, copied in only at verification time
      solution/solve.sh        # reference solution (optional, but strongly recommended)
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

TASK_FILE = "task.yaml"


class TaskSpecError(ValueError):
    """The task directory or its task.yaml is invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Environment(_Strict):
    dockerfile: str = "environment/Dockerfile"
    context: str = "environment"
    workdir: str = "/workspace"
    # User the agent (and the reference solution) runs as. None = the image's default user.
    # Running the agent as an unprivileged user is the main defence against tampering.
    agent_user: str | None = None


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
        try:
            raw = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
            task = cls.model_validate(raw)
        except yaml.YAMLError as exc:
            raise TaskSpecError(f"{spec_file}: invalid YAML: {exc}") from exc
        except ValidationError as exc:
            raise TaskSpecError(f"{spec_file}: {exc}") from exc
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
