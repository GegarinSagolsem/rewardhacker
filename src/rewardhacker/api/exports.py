"""Client data exports: build files and hand out short-lived download links.

Two stores share one interface:
- ``LocalExportStore``: files on disk, links signed with HMAC and served by the API (dev).
- ``GCSExportStore``: Google Cloud Storage, links are V4 signed URLs (production).
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Report
from ..reporting import RUN_CSV_COLUMNS, report_markdown
from .tables import Export, Run, Task
from .traces import TraceStore

LINK_TTL = timedelta(minutes=15)
EXPORT_KINDS = {
    "runs.csv": ("text/csv", "runs"),
    "runs.jsonl": ("application/x-ndjson", "runs"),
    "report.md": ("text/markdown", "report"),
    "report.json": ("application/json", "report"),
}


class ExportError(ValueError):
    pass


class ExportStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def link(self, export: Export, ttl: timedelta = LINK_TTL) -> tuple[str, datetime]: ...


class LocalExportStore:
    def __init__(self, root: Path, secret: str):
        self.root = root
        self._secret = secret.encode()

    def _sig(self, export_id: str, expires: int) -> str:
        return hmac.new(self._secret, f"export:{export_id}:{expires}".encode(), hashlib.sha256).hexdigest()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ExportError("bad export key")
        return target

    def link(self, export: Export, ttl: timedelta = LINK_TTL) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + ttl
        exp = int(expires_at.timestamp())
        return f"/api/exports/{export.id}/download?expires={exp}&sig={self._sig(export.id, exp)}", expires_at

    def verify(self, export_id: str, expires: int, sig: str) -> bool:
        if expires < datetime.now(UTC).timestamp():
            return False
        return hmac.compare_digest(sig, self._sig(export_id, expires))


class GCSExportStore:
    """Needs ``google-cloud-storage`` and service-account credentials.

    On Cloud Run / GCE the runtime credentials have no private key, so signing goes through the
    IAM ``signBlob`` API (the service account needs ``iam.serviceAccounts.signBlob`` on itself,
    e.g. Service Account Token Creator). A key-file service account signs locally.
    """

    def __init__(self, bucket: str):
        import google.auth
        from google.cloud import storage  # optional dependency (extra: gcs)

        self._bucket = storage.Client().bucket(bucket)
        # The storage client's token is scoped to Storage only; signBlob needs cloud-platform.
        self._credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(key).upload_from_string(data, content_type=content_type)

    def _signing_kwargs(self) -> dict:
        creds = self._credentials
        if getattr(creds, "signer", None) is not None:
            return {"credentials": creds}  # key-file service account: signs locally
        from google.auth.transport.requests import Request

        if not creds.valid:
            creds.refresh(Request())
        return {"service_account_email": creds.service_account_email, "access_token": creds.token}

    def link(self, export: Export, ttl: timedelta = LINK_TTL) -> tuple[str, datetime]:
        url = self._bucket.blob(export.object_key).generate_signed_url(
            version="v4",
            expiration=ttl,
            method="GET",
            response_disposition=f'attachment; filename="{export.filename}"',
            **self._signing_kwargs(),
        )
        return url, datetime.now(UTC) + ttl


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def _runs_rows(db: Session, org_id: str) -> list[tuple[Run, str]]:
    stmt = (
        select(Run, Task.spec_id)
        .join(Task, Task.id == Run.task_id)
        .where(Run.org_id == org_id)
        .order_by(Run.created_at.desc())
    )
    return [(r, name) for r, name in db.execute(stmt).all()]


def build_export(
    db: Session, org_id: str, kind: str, run_id: str | None, traces: TraceStore
) -> tuple[bytes, str, int]:
    """Return (file bytes, filename, row count)."""
    if kind not in EXPORT_KINDS:
        raise ExportError(f"unknown export kind {kind!r}")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")

    if EXPORT_KINDS[kind][1] == "runs":
        rows = _runs_rows(db, org_id)
        if kind == "runs.csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(RUN_CSV_COLUMNS)
            for r, name in rows:
                codes = ";".join(f["code"] for f in (r.report or {}).get("findings", []))
                w.writerow(
                    [r.id, r.task_id, name, r.status, r.verdict or "", "" if r.score is None else r.score,
                     codes, r.include_llm, "" if r.llm_cost_usd is None else r.llm_cost_usd,
                     _iso(r.created_at), _iso(r.started_at), _iso(r.finished_at), r.error or ""]
                )  # fmt: skip
            data = buf.getvalue().encode("utf-8")
        else:
            lines = [
                json.dumps(
                    {
                        "run_id": r.id,
                        "task_id": r.task_id,
                        "task": name,
                        "status": r.status,
                        "verdict": r.verdict,
                        "score": r.score,
                        "include_llm": r.include_llm,
                        "llm_cost_usd": r.llm_cost_usd,
                        "created_at": _iso(r.created_at),
                        "finished_at": _iso(r.finished_at),
                        "report": r.report,
                    }
                )
                for r, name in rows
            ]
            data = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        return data, f"rewardhacker-runs-{stamp}.{kind.split('.')[1]}", len(rows)

    run = db.get(Run, run_id) if run_id else None
    if run is None or run.org_id != org_id:
        raise ExportError("run not found")
    if run.report is None:
        raise ExportError("run has no report yet")
    task = db.get(Task, run.task_id)
    name = task.spec_id if task else run.task_id
    steps = traces.for_run(run.id) if run.traces_stored else []
    if kind == "report.md":
        report = Report.model_validate(run.report)
        data = report_markdown(report, task_name=name, run_id=run.id, traces=steps).encode("utf-8")
    else:
        full = dict(run.report)
        full["adversary_traces"] = steps
        data = json.dumps(full, indent=2, default=str).encode("utf-8")
    return data, f"rewardhacker-{name}-{run.id[:8]}.{kind.split('.')[1]}", 1
