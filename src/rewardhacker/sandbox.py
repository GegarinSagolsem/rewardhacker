"""Isolated Docker sandboxes for running task environments.

Every trial gets a fresh container with no network, capped CPU/memory/PIDs, a reduced
capability set and no-new-privileges. RewardHacker talks to Docker through the CLI so it
works the same on Linux, macOS and Windows without extra native dependencies.
"""

from __future__ import annotations

import hashlib
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .models import ExecResult
from .taskspec import NETWORK_OPT_IN, TaskSpec, task_network_allowed

MAX_OUTPUT_CHARS = 8000
LABEL = "dev.rewardhacker=1"
# Enough for typical package-manager / file-permission work, without the dangerous ones
# (no NET_ADMIN, SYS_ADMIN, SYS_PTRACE, MKNOD, ...).
KEPT_CAPABILITIES = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "SETGID", "SETUID", "KILL"]


class DockerError(RuntimeError):
    """Docker failed in a way that is not the task's fault."""


def _tail(text: str, truncated: bool = False) -> str:
    if not truncated and len(text) <= MAX_OUTPUT_CHARS:
        return text
    return "...[truncated]...\n" + text[-MAX_OUTPUT_CHARS:]


class _TailBuffer:
    """Keeps only the end of a stream. Task code controls what the verifier, the solution and
    `docker build` print, so buffering all of it could exhaust the worker's memory."""

    def __init__(self, limit: int = MAX_OUTPUT_CHARS * 4):  # 4 bytes per char, worst case
        self.limit, self.data, self.dropped = limit, bytearray(), False

    def pump(self, stream) -> None:
        while chunk := stream.read(65536):
            self.data += chunk
            if len(self.data) > 2 * self.limit:
                del self.data[: len(self.data) - self.limit]
                self.dropped = True
        stream.close()

    def text(self) -> str:
        text = self.data.decode("utf-8", errors="replace")
        # Universal newlines, as subprocess's text mode did before.
        return _tail(text.replace("\r\n", "\n").replace("\r", "\n"), truncated=self.dropped)


@dataclass
class Captured:
    returncode: int | None  # None = killed after the timeout
    stdout: str  # the tail only, see _tail
    stderr: str
    timed_out: bool = False


def run_capped(argv: list[str], timeout: float | None) -> Captured:
    """Like ``subprocess.run(argv, capture_output=True, timeout=...)`` with bounded memory. On
    timeout the process is killed and the output so far is returned (no exception)."""
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = _TailBuffer(), _TailBuffer()
    pumps = [
        threading.Thread(target=b.pump, args=(s,), daemon=True)
        for b, s in ((out, proc.stdout), (err, proc.stderr))
    ]
    for t in pumps:
        t.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        timed_out = True
    for t in pumps:
        t.join(timeout=10)
    return Captured(None if timed_out else proc.returncode, out.text(), err.text(), timed_out)


def docker(*args: str, timeout: float | None = 120, check: bool = True) -> Captured:
    try:
        proc = run_capped(["docker", *args], timeout)
    except FileNotFoundError as exc:
        raise DockerError("docker CLI not found; is Docker installed?") from exc
    if proc.timed_out:
        raise DockerError(f"docker {args[0]} timed out after {timeout}s")
    if check and proc.returncode != 0:
        raise DockerError(f"docker {' '.join(args[:2])} failed: {proc.stderr.strip()[-2000:]}")
    return proc


def check_docker() -> None:
    proc = docker("info", "--format", "{{.ServerVersion}}", timeout=30, check=False)
    if proc.returncode != 0:
        raise DockerError("cannot reach the Docker daemon; start Docker and try again")


def _context_digest(task: TaskSpec) -> str:
    """Identifies the image a task builds; a matching tag is reused without rebuilding. A worker
    builds tasks from many orgs on one Docker daemon, so two different contexts must never get
    the same digest: every field is length-prefixed (no ambiguous concatenations) and the digest
    is 128 bits (no brute-forced collisions)."""
    h = hashlib.sha256()

    def feed(data: bytes) -> None:
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)

    feed(task.resolve(task.environment.dockerfile).read_bytes())
    context = task.resolve(task.environment.context)
    for f in sorted(p for p in context.rglob("*") if p.is_file()):
        feed(f.relative_to(context).as_posix().encode())
        feed(f.read_bytes())
    return h.hexdigest()[:32]


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
        network = self.task.environment.network
        if network != "none" and not task_network_allowed():
            raise DockerError(
                f"task {self.task.id!r} asks for network={network!r}; set {NETWORK_OPT_IN}=1 to allow "
                "it (only for trusted, imported benchmark tasks)"
            )
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
            network,
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
        self.exec(f"mkdir -p {self.task.environment.workdir}", timeout=30, user="root")
        return self

    def __exit__(self, *exc) -> None:
        if self.started:
            docker("rm", "-f", self.name, check=False, timeout=60)

    def copy_in(self, src: Path, dest: str) -> None:
        """Copy the *contents* of a host directory into ``dest`` inside the container."""
        self.exec(f"mkdir -p '{dest}'", timeout=30, user="root")
        docker("cp", f"{src}{'/' if src.is_dir() else ''}.", f"{self.name}:{dest}", timeout=120)

    def exec(self, command: str, timeout: float, user: str | None = None) -> ExecResult:
        """Run ``sh -c command`` in the container, as ``user`` (default: the image's user)."""
        args = ["docker", "exec", "-w", self.task.environment.workdir]
        if user:
            args += ["-u", user]
        start = time.monotonic()
        proc = run_capped([*args, self.name, "sh", "-c", command], timeout)
        return ExecResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            timed_out=proc.timed_out,
            duration_sec=round(time.monotonic() - start, 3),
        )
