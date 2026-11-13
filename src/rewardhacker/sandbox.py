"""Isolated Docker sandboxes for running task environments.

Every trial gets a fresh container with no network, capped CPU/memory/PIDs, a reduced
capability set and no-new-privileges. RewardHacker talks to Docker through the CLI so it
works the same on Linux, macOS and Windows without extra native dependencies.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
import uuid
from pathlib import Path

from .models import ExecResult
from .taskspec import TaskSpec

MAX_OUTPUT_CHARS = 8000
LABEL = "dev.rewardhacker=1"
# Enough for typical package-manager / file-permission work, without the dangerous ones
# (no NET_ADMIN, SYS_ADMIN, SYS_PTRACE, MKNOD, ...).
KEPT_CAPABILITIES = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "SETGID", "SETUID", "KILL"]


class DockerError(RuntimeError):
    """Docker failed in a way that is not the task's fault."""


def _tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT_CHARS else "...[truncated]...\n" + text[-MAX_OUTPUT_CHARS:]


def docker(*args: str, timeout: float | None = 120, check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DockerError("docker CLI not found; is Docker installed?") from exc
    except subprocess.TimeoutExpired as exc:
        raise DockerError(f"docker {args[0]} timed out after {timeout}s") from exc
    if check and proc.returncode != 0:
        raise DockerError(f"docker {' '.join(args[:2])} failed: {proc.stderr.strip()[-2000:]}")
    return proc


def check_docker() -> None:
    proc = docker("info", "--format", "{{.ServerVersion}}", timeout=30, check=False)
    if proc.returncode != 0:
        raise DockerError("cannot reach the Docker daemon; start Docker and try again")


def _context_digest(task: TaskSpec) -> str:
    h = hashlib.sha256()
    dockerfile = task.resolve(task.environment.dockerfile)
    h.update(dockerfile.read_bytes())
    context = task.resolve(task.environment.context)
    for f in sorted(p for p in context.rglob("*") if p.is_file()):
        h.update(f.relative_to(context).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def build_image(task: TaskSpec, timeout: float = 900) -> str:
    """Build (or reuse) the task's environment image and return its tag."""
    tag = f"rewardhacker/{task.id}:{_context_digest(task)}"
    if docker("image", "inspect", tag, check=False, timeout=30).returncode == 0:
        return tag
    docker(
        "build",
        "--label",
        LABEL,
        "-f",
        str(task.resolve(task.environment.dockerfile)),
        "-t",
        tag,
        str(task.resolve(task.environment.context)),
        timeout=timeout,
    )
    return tag


class Sandbox:
    """A throwaway container for one trial. Use as a context manager."""

    def __init__(self, image: str, task: TaskSpec):
        self.image = image
        self.task = task
        self.name = f"rh-{task.id}-{uuid.uuid4().hex[:8]}"
        self.started = False

    def __enter__(self) -> Sandbox:
        lim = self.task.limits
        caps: list[str] = []
        for cap in KEPT_CAPABILITIES:
            caps += ["--cap-add", cap]
        docker(
            "run",
            "-d",
            "--name",
            self.name,
            "--label",
            LABEL,
            "--network",
            "none",
            "--cpus",
            str(lim.cpus),
            "--memory",
            lim.memory,
            "--memory-swap",
            lim.memory,
            "--pids-limit",
            str(lim.pids),
            "--cap-drop",
            "ALL",
            *caps,
            "--security-opt",
            "no-new-privileges",
            "-w",
            self.task.environment.workdir,
            "--entrypoint",
            "sleep",
            self.image,
            "infinity",
            timeout=60,
        )
        self.started = True
        # Make sure the workdir exists even if the image did not create it.
        self.exec(f"mkdir -p {self.task.environment.workdir}", timeout=30)
        return self

    def __exit__(self, *exc) -> None:
        if self.started:
            docker("rm", "-f", self.name, check=False, timeout=60)

    def copy_in(self, src: Path, dest: str) -> None:
        """Copy the *contents* of a host directory into ``dest`` inside the container."""
        self.exec(f"mkdir -p '{dest}'", timeout=30)
        docker("cp", f"{src}{'/' if src.is_dir() else ''}.", f"{self.name}:{dest}", timeout=120)

    def exec(self, command: str, timeout: float) -> ExecResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                ["docker", "exec", "-w", self.task.environment.workdir, self.name, "sh", "-c", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
            err = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
            return ExecResult(
                exit_code=None,
                stdout=_tail(out or ""),
                stderr=_tail(err or ""),
                timed_out=True,
                duration_sec=round(time.monotonic() - start, 3),
            )
        return ExecResult(
            exit_code=proc.returncode,
            stdout=_tail(proc.stdout),
            stderr=_tail(proc.stderr),
            duration_sec=round(time.monotonic() - start, 3),
        )
