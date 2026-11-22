"""The probe worker: claims queued runs from Postgres and executes them in Docker."""

from __future__ import annotations

import logging
import os
import socket
import time

from .db import make_engine, make_sessionmaker
from .jobs import claim_next, execute, recover_stale
from .settings import get_api_settings
from .storage import TaskFiles
from .traces import make_trace_store

log = logging.getLogger(__name__)


def run_worker(once: bool = False, poll_seconds: float = 2.0, idle_exit: float = 0.0) -> int:
    """Process runs until interrupted. With ``once``, exit when the queue has been empty for
    ``idle_exit`` seconds (0 = immediately). Per-run Cloud Build workers use a grace period so a
    run queued just as the queue drained is still picked up by this build."""
    settings = get_api_settings()
    sessions = make_sessionmaker(make_engine(settings.database_url))
    traces = make_trace_store(settings.mongodb_uri, settings.mongodb_db)
    task_files = TaskFiles(settings.storage_dir, settings.gcs_bucket)
    worker_id = f"{socket.gethostname()}-{os.getpid()}"

    with sessions() as db:
        if n := recover_stale(db):
            log.warning("requeued %d stale run(s)", n)

    processed = 0
    idle_since = time.monotonic()
    while True:
        with sessions() as db:
            run = claim_next(db, worker_id)
            if run is not None:
                log.info("run %s: started (task %s, llm=%s)", run.id, run.task_id, run.include_llm)
                execute(db, run, traces, open_task=task_files.open)
                log.info("run %s: %s %s", run.id, run.status, run.verdict or run.error or "")
                processed += 1
                idle_since = time.monotonic()
                continue
        if once and time.monotonic() - idle_since >= idle_exit:
            return processed
        time.sleep(poll_seconds)
