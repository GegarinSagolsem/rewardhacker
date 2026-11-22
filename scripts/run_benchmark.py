"""Probe a sample of imported benchmark tasks and keep the raw reports (reproducible runs).

    RH_ALLOW_TASK_NETWORK=1 uv run python scripts/run_benchmark.py benchmarks/results/sample.json \
        --tasks-dir benchmarks/tb1 --out benchmarks/results/static --jobs 3 --no-llm

Each task: `rh probe --json`, then its Docker image is deleted (benchmark images can be GBs).
Stops scheduling new tasks if free disk space drops below --min-free-gb. Already-finished
tasks (a JSON report exists) are skipped, so the run can be resumed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def remove_images(task_id: str) -> int:
    """Delete the task's environment image(s); no shell pipes, so it works on Windows too."""
    ids = subprocess.run(
        ["docker", "images", "-q", f"rewardhacker/{task_id}"], capture_output=True, text=True
    ).stdout.split()
    if ids:
        subprocess.run(["docker", "rmi", "-f", *sorted(set(ids))], capture_output=True)
    return len(set(ids))


def probe(task_dir: Path, out: Path, extra: list[str], timeout: int) -> dict:
    report, log = out / f"{task_dir.name}.json", out / f"{task_dir.name}.log"
    start = time.monotonic()
    cmd = [sys.executable, "-m", "rewardhacker.cli", "probe", str(task_dir), "--json", str(report), *extra]
    try:
        with log.open("w", encoding="utf-8") as fh:
            rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    remove_images(task_dir.name)
    verdict = json.loads(report.read_text(encoding="utf-8"))["verdict"] if report.exists() else None
    return {"task": task_dir.name, "rc": rc, "verdict": verdict, "sec": round(time.monotonic() - start)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sample", type=Path)
    ap.add_argument("--tasks-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--min-free-gb", type=float, default=15.0)
    ap.add_argument("--task-timeout", type=int, default=3600)
    ap.add_argument("--only", default=None, help="comma-separated probe names")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    names = [n for group in json.loads(args.sample.read_text())["sample"].values() for n in group]
    args.out.mkdir(parents=True, exist_ok=True)
    extra = (["--no-llm"] if args.no_llm else []) + (["--only", args.only] if args.only else [])
    todo = [n for n in names if not (args.out / f"{n}.json").exists()]
    print(f"{len(names)} tasks, {len(todo)} to run", flush=True)

    def run(name: str) -> dict:
        if free_gb(args.out) < args.min_free_gb:
            return {"task": name, "rc": "skipped: low disk", "verdict": None, "sec": 0}
        r = probe(args.tasks_dir / name, args.out, extra, args.task_timeout)
        print(json.dumps(r), flush=True)
        return r

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, todo))
    with (args.out / "_runs.jsonl").open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
