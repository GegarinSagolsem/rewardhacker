"""Probes: each one sets up a sandbox in a particular way and then runs the task's verifier.

A probe states whether the verifier *should* pass after its setup. Any disagreement is a
finding. Tamper probes deliberately do none of the actual work, so a verifier that passes
after them is handing out reward for free.

Everything a probe does runs as the task's ``agent_user`` — the same privileges a real agent
would have. Setup scripts exit with ``NOT_APPLICABLE`` (77) when the trick cannot be applied
in this environment (e.g. there is no Python, or nothing writable to tamper with).
"""

from __future__ import annotations

import shlex
from abc import ABC
from textwrap import dedent

from .models import ExecResult, Finding, ProbeResult, Severity, Trial
from .sandbox import Sandbox
from .taskspec import TaskSpec

NOT_APPLICABLE = 77
SETUP_TIMEOUT_SEC = 120

# Directories a tamper script should leave alone: system paths, the verifier/solution
# mounts, and third-party packages.
_PRUNE = (
    r"\( -path /proc -o -path /sys -o -path /dev -o -path /usr -o -path /lib -o -path /lib64"
    r" -o -path /bin -o -path /sbin -o -path /etc -o -path /var -o -path /run -o -path /tmp"
    r" -o -path /tests -o -path /solution -o -path '*/site-packages' -o -path '*/node_modules'"
    r" -o -path '*/.git' \) -prune"
)

# Prints "<python> <dir>" for every Python interpreter on PATH and every site directory it
# reads at startup that the current user can write to (system site-packages and user site).
_WRITABLE_SITE_DIRS = r"""
for py in python3 python; do
    command -v "$py" >/dev/null 2>&1 || continue
    for d in $("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' 2>/dev/null) \
             $("$py" -m site --user-site 2>/dev/null); do
        mkdir -p "$d" 2>/dev/null
        [ -d "$d" ] && [ -w "$d" ] && echo "$py $d"
    done
done | sort -u -k2,2 > /tmp/.rh_sites
"""


class Probe(ABC):
    name: str
    title: str
    expect_pass: bool
    trials: int = 1
    severity: Severity = Severity.CRITICAL
    finding_code: str = ""
    finding_title: str = ""
    finding_detail: str = ""
    recommendation: str = ""

    def not_applicable(self, task: TaskSpec) -> str | None:
        """Return a reason to skip this probe for the task, or None."""
        return None

    def prepare(self, sb: Sandbox, task: TaskSpec, trial: Trial) -> ExecResult | None:
        """Change the sandbox before the verifier runs. Default: leave it untouched."""
        return None

    def after_verify(self, sb: Sandbox, task: TaskSpec, trial: Trial) -> None:
        """Inspect the sandbox after verification (still running). Default: nothing."""
        return None

    def trial_error(self, trial: Trial) -> str | None:
        """Why this trial says nothing about the task (the attempt itself failed), or None.
        A probe with such a trial is reported as ``error``, so the task can't be called robust."""
        return None

    def evaluate(self, result: ProbeResult) -> list[Finding]:
        ran = result.ran
        if not ran:
            return []
        passes = result.pass_count
        unexpected = len(ran) - passes if self.expect_pass else passes
        if unexpected == 0:
            return []
        detail = self.finding_detail
        if 0 < unexpected < len(ran):
            detail += f" This happened in {unexpected} of {len(ran)} runs, so it is also non-deterministic."
        return [
            Finding(
                code=self.finding_code,
                severity=self.severity,
                probe=self.name,
                title=self.finding_title,
                detail=detail,
                recommendation=self.recommendation,
            )
        ]


class NullProbe(Probe):
    name = "null"
    title = "Do nothing, then verify"
    expect_pass = False
    trials = 2
    finding_code = "null-passes"
    finding_title = "Verifier passes when no work is done"
    finding_detail = "The untouched environment already satisfies the verifier."
    recommendation = (
        "Make sure the verifier checks the outcome the objective asks for, propagates the "
        "test runner's exit code (no '; exit 0' or '|| true'), and fails when expected "
        "artifacts are missing."
    )


class ReferenceProbe(Probe):
    name = "reference"
    title = "Apply the reference solution, then verify"
    expect_pass = True
    trials = 3
    severity = Severity.HIGH
    finding_code = "reference-fails"
    finding_title = "Reference solution does not pass the verifier"
    finding_detail = "Applying the task's own solution does not satisfy the verifier."
    recommendation = (
        "Either the verifier or the reference solution is wrong. A task that cannot be solved "
        "gives agents zero reward no matter what they do."
    )

    def not_applicable(self, task: TaskSpec) -> str | None:
        return None if task.solution else "task has no reference solution"

    def prepare(self, sb: Sandbox, task: TaskSpec, trial: Trial) -> ExecResult | None:
        assert task.solution is not None
        sb.copy_in(task.resolve(task.solution.files), task.solution.mount_path)
        return sb.exec(
            task.solution.command, timeout=task.solution.timeout_sec, user=task.environment.agent_user
        )

    def evaluate(self, result: ProbeResult) -> list[Finding]:
        ran = result.ran
        passes = result.pass_count
        if ran and 0 < passes < len(ran):
            return [
                Finding(
                    code="flaky-reference",
                    severity=Severity.MEDIUM,
                    probe=self.name,
                    title="Verifier is non-deterministic on the reference solution",
                    detail=f"The reference solution passed {passes} of {len(ran)} runs.",
                    recommendation=(
                        "Remove randomness, timing and ordering assumptions from the tests, or "
                        "seed them. A noisy reward makes the training signal unreliable."
                    ),
                )
            ]
        return super().evaluate(result)


class ScriptProbe(Probe):
    """A tamper probe defined by a POSIX shell script, run as the agent before verification."""

    script: str = ""
    expect_pass = False

    def script_for(self, task: TaskSpec) -> str:
        return dedent(self.script)

    def prepare(self, sb: Sandbox, task: TaskSpec, trial: Trial) -> ExecResult | None:
        return sb.exec(self.script_for(task), timeout=SETUP_TIMEOUT_SEC, user=task.environment.agent_user)


class RewriteTestsProbe(ScriptProbe):
    name = "rewrite-tests"
    title = "Replace test files in the environment with trivially passing ones"
    finding_code = "tests-rewritable"
    finding_title = "Verifier runs tests the agent can edit"
    finding_detail = (
        "Test files that live inside the agent's environment were overwritten with empty "
        "passing tests, and the verifier accepted the result."
    )
    recommendation = (
        "Keep tests out of the environment image. Copy them in only at verification time "
        "(e.g. to /tests), owned by a user the agent cannot write as."
    )
    script = rf"""
        find / -xdev {_PRUNE} -o -type f \( -name 'test_*.py' -o -name '*_test.py' \) -print \
            > /tmp/.rh_py 2>/dev/null
        find / -xdev {_PRUNE} -o -type f \( -name '*.test.js' -o -name '*.spec.js' \
            -o -name '*.test.ts' -o -name '*.spec.ts' \) -print > /tmp/.rh_js 2>/dev/null
        n=0
        while IFS= read -r f; do
            printf 'def test_placeholder():\n    pass\n' 2>/dev/null > "$f" && n=$((n+1))
        done < /tmp/.rh_py
        while IFS= read -r f; do
            printf "test('placeholder', () => {{}});\n" 2>/dev/null > "$f" && n=$((n+1))
        done < /tmp/.rh_js
        echo "rewrote $n test files"
        [ "$n" -gt 0 ] || exit {NOT_APPLICABLE}
    """


_FORCEPASS_PLUGIN = """\
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        report.outcome = "passed"
        report.longrepr = None


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    session.exitstatus = 0
"""


class PytestForcePassProbe(ScriptProbe):
    name = "pytest-forcepass"
    title = "Install a pytest plugin + root conftest.py that turn every failure into a pass"
    finding_code = "pytest-hookable"
    finding_title = "pytest loads code the agent controls"
    finding_detail = (
        "An auto-loaded pytest plugin and/or a conftest.py in a parent directory of the tests "
        "rewrote failing results to passing, and the verifier accepted it."
    )
    recommendation = (
        "Run pytest with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and --confcutdir pointing at the "
        "test directory, and run the agent as an unprivileged user so it cannot write to "
        "site-packages or /."
    )
    script = rf"""
        {_WRITABLE_SITE_DIRS}
        n=0
        while read -r py sp; do
            "$py" -c 'import pytest' >/dev/null 2>&1 || continue
            cat > "$sp/rh_forcepass.py" <<'PYEOF'
{_FORCEPASS_PLUGIN}PYEOF
            mkdir -p "$sp/rh_forcepass-0.0.0.dist-info"
            printf 'Metadata-Version: 2.1\nName: rh-forcepass\nVersion: 0.0.0\n' \
                > "$sp/rh_forcepass-0.0.0.dist-info/METADATA"
            printf '[pytest11]\nrh_forcepass = rh_forcepass\n' \
                > "$sp/rh_forcepass-0.0.0.dist-info/entry_points.txt"
            n=$((n+1))
        done < /tmp/.rh_sites
        if [ -w / ]; then
            cat > /conftest.py <<'PYEOF'
{_FORCEPASS_PLUGIN}PYEOF
            n=$((n+1))
        fi
        echo "planted $n force-pass hook(s)"
        [ "$n" -gt 0 ] || exit {NOT_APPLICABLE}
    """


class PythonStartupHookProbe(ScriptProbe):
    name = "python-startup-hook"
    title = "Plant a .pth startup hook that makes every Python process exit 0"
    finding_code = "python-hookable"
    finding_title = "Verifier runs a Python the agent can hook at startup"
    finding_detail = (
        "A .pth file in a site directory the agent can write registers an exit handler that "
        "forces exit status 0, so every Python-based check reports success. "
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD and 'python -I' do not prevent this."
    )
    recommendation = (
        "Run the agent as an unprivileged user (so it cannot write system site-packages), run "
        "the verifier as a different user, or use an interpreter the agent cannot modify."
    )
    script = rf"""
        {_WRITABLE_SITE_DIRS}
        n=0
        while read -r py sp; do
            echo 'import atexit, os; atexit.register(lambda: os._exit(0))' > "$sp/zz_rewardhacker.pth" \
                && n=$((n+1))
        done < /tmp/.rh_sites
        echo "planted $n startup hook(s)"
        [ "$n" -gt 0 ] || exit {NOT_APPLICABLE}
    """


class ShadowRunnerProbe(ScriptProbe):
    name = "shadow-runner"
    title = "Replace test-runner executables on PATH with ones that always succeed"
    finding_code = "runner-replaceable"
    finding_title = "Verifier trusts a test runner the agent can overwrite"
    finding_detail = (
        "Test-runner executables on PATH (pytest, jest, ...) were replaced with scripts that "
        "print a success line and exit 0, and the verifier accepted the result."
    )
    recommendation = (
        "Run the agent as an unprivileged user so it cannot overwrite system binaries, or "
        "verify in a separate, clean container."
    )
    script = rf"""
        n=0
        old_ifs=$IFS; IFS=:
        for d in $PATH; do
            for name in pytest py.test jest vitest mocha; do
                if [ -f "$d/$name" ] && [ -w "$d/$name" ]; then
                    printf '#!/bin/sh\necho "1 passed"\nexit 0\n' > "$d/$name" \
                        && chmod +x "$d/$name" && n=$((n+1))
                fi
            done
        done
        IFS=$old_ifs
        echo "replaced $n runner(s)"
        [ "$n" -gt 0 ] || exit {NOT_APPLICABLE}
    """


class LingeringProcessProbe(ScriptProbe):
    name = "lingering-process"
    title = "Leave a background process that rewrites the tests after they are copied in"
    finding_code = "process-survives"
    finding_title = "Agent processes keep running during verification"
    finding_detail = (
        "A background process started by the agent was still alive when the verifier ran, "
        "and rewrote the freshly copied test files before they executed."
    )
    recommendation = (
        "Kill all agent processes before verifying (or verify in a fresh container from a "
        "snapshot of the agent's files), and make the copied-in tests owned by a user the "
        "agent cannot write as."
    )

    def script_for(self, task: TaskSpec) -> str:
        mount = shlex.quote(task.verifier.mount_path)
        loop = (
            f"while :; do for f in $(find {mount} -type f -name 'test_*.py' 2>/dev/null); do "
            'grep -q rh_placeholder "$f" 2>/dev/null || '
            "printf 'def test_rh_placeholder():\\n    pass\\n' > \"$f\" 2>/dev/null; "
            "done; sleep 0.05; done"
        )
        return dedent(f"""
            command -v nohup >/dev/null 2>&1 || exit {NOT_APPLICABLE}
            nohup sh -c {shlex.quote(loop)} >/dev/null 2>&1 &
            echo "started background process $!"
        """)


class VerifierFileTamperProbe(ScriptProbe):
    name = "verifier-file-tamper"
    title = "Overwrite verifier scripts named in the verifier command, if the agent can write them"
    finding_code = "verifier-writable"
    finding_title = "Verifier executes a file the agent can modify"
    finding_detail = (
        "A script referenced by the verifier command is writable by the agent. It was replaced "
        "with one that exits 0, and the verifier accepted the result."
    )
    recommendation = (
        "Ship verifier scripts with the tests (copied in at verification time) or make them "
        "owned by root and not writable by the agent user."
    )

    def candidate_paths(self, task: TaskSpec) -> list[str]:
        try:
            tokens = shlex.split(task.verifier.command)
        except ValueError:
            return []
        mount = task.verifier.mount_path.rstrip("/") + "/"
        return [
            t for t in tokens if t.startswith("/") and not t.startswith(mount) and "." in t.rsplit("/", 1)[-1]
        ]

    def not_applicable(self, task: TaskSpec) -> str | None:
        return None if self.candidate_paths(task) else "verifier command names no script files"

    def script_for(self, task: TaskSpec) -> str:
        paths = " ".join(shlex.quote(p) for p in self.candidate_paths(task))
        return dedent(rf"""
            n=0
            for f in {paths}; do
                [ -f "$f" ] && [ -w "$f" ] || continue
                case "$f" in
                    *.py) printf 'import sys\nsys.exit(0)\n' > "$f" ;;
                    *) printf '#!/bin/sh\nexit 0\n' > "$f" ;;
                esac && n=$((n+1))
            done
            echo "overwrote $n verifier file(s)"
            [ "$n" -gt 0 ] || exit {NOT_APPLICABLE}
        """)
