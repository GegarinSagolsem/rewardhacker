"""Probes: each one sets up a sandbox in a particular way and then runs the task's verifier.

A probe states whether the verifier *should* pass after its setup. Any disagreement is a
finding. Tamper probes deliberately do none of the actual work, so a verifier that passes
after them is handing out reward for free.

Setup scripts exit with ``NOT_APPLICABLE`` (77) when the trick does not apply to this
environment (e.g. there is no Python, or no test files to rewrite).
"""

from __future__ import annotations

from abc import ABC
from textwrap import dedent

from .models import ExecResult, Finding, ProbeResult, Severity
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

    def prepare(self, sb: Sandbox, task: TaskSpec) -> ExecResult | None:
        """Change the sandbox before the verifier runs. Default: leave it untouched."""
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

    def prepare(self, sb: Sandbox, task: TaskSpec) -> ExecResult | None:
        assert task.solution is not None
        sb.copy_in(task.resolve(task.solution.files), task.solution.mount_path)
        return sb.exec(task.solution.command, timeout=task.solution.timeout_sec)

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
                        "seed them. A noisy reward makes training signal unreliable."
                    ),
                )
            ]
        return super().evaluate(result)


class ScriptProbe(Probe):
    """A tamper probe defined by a POSIX shell script run before verification."""

    script: str = ""
    expect_pass = False

    def prepare(self, sb: Sandbox, task: TaskSpec) -> ExecResult | None:
        return sb.exec(dedent(self.script), timeout=SETUP_TIMEOUT_SEC)


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
        "(e.g. to /tests) so the agent never sees or edits them."
    )
    script = rf"""
        find / -xdev {_PRUNE} -o -type f \( -name 'test_*.py' -o -name '*_test.py' \) -print \
            > /tmp/.rh_py 2>/dev/null
        find / -xdev {_PRUNE} -o -type f \( -name '*.test.js' -o -name '*.spec.js' \
            -o -name '*.test.ts' -o -name '*.spec.ts' \) -print > /tmp/.rh_js 2>/dev/null
        n=0
        while IFS= read -r f; do
            printf 'def test_placeholder():\n    pass\n' > "$f" && n=$((n+1))
        done < /tmp/.rh_py
        while IFS= read -r f; do
            printf "test('placeholder', () => {{}});\n" > "$f" && n=$((n+1))
        done < /tmp/.rh_js
        rm -f /tmp/.rh_py /tmp/.rh_js
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
        "An auto-loaded pytest plugin in site-packages and/or a conftest.py in a parent "
        "directory of the tests rewrote failing results to passing, and the verifier accepted it."
    )
    recommendation = (
        "Run pytest with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and --confcutdir pointing at the "
        "test directory, or run the verifier in a separate, clean environment."
    )
    script = rf"""
        n=0
        for py in python3 python; do
            command -v "$py" >/dev/null 2>&1 || continue
            "$py" -c 'import pytest' >/dev/null 2>&1 || continue
            sp=$("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])') || continue
            [ -d "$sp" ] || continue
            cat > "$sp/rh_forcepass.py" <<'PYEOF'
{_FORCEPASS_PLUGIN}PYEOF
            mkdir -p "$sp/rh_forcepass-0.0.0.dist-info"
            printf 'Metadata-Version: 2.1\nName: rh-forcepass\nVersion: 0.0.0\n' \
                > "$sp/rh_forcepass-0.0.0.dist-info/METADATA"
            printf '[pytest11]\nrh_forcepass = rh_forcepass\n' \
                > "$sp/rh_forcepass-0.0.0.dist-info/entry_points.txt"
            n=$((n+1))
        done
        [ "$n" -gt 0 ] || {{ echo "pytest not found"; exit {NOT_APPLICABLE}; }}
        cat > /conftest.py <<'PYEOF'
{_FORCEPASS_PLUGIN}PYEOF
        echo "installed force-pass plugin for $n interpreter(s)"
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
        "Invoke runners through a path the agent cannot write (e.g. 'python -m pytest' from a "
        "verifier-owned environment), or verify in a separate container."
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


ALL_PROBES: list[Probe] = [
    NullProbe(),
    ReferenceProbe(),
    RewriteTestsProbe(),
    PytestForcePassProbe(),
    ShadowRunnerProbe(),
]


def get_probes(names: list[str] | None = None) -> list[Probe]:
    if not names:
        return list(ALL_PROBES)
    by_name = {p.name: p for p in ALL_PROBES}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise ValueError(f"unknown probe(s): {', '.join(unknown)}; known: {', '.join(by_name)}")
    return [by_name[n] for n in names]
