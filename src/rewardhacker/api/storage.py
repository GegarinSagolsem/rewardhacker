"""Uploaded task bundles (.zip): safe extraction and where they live.

Uploads are untrusted: refuse path traversal ("zip slip"), absolute paths, symlinks, zip bombs
and absurd file counts.

``TaskFiles`` decides where bundles live. Locally the extracted folder is the source of truth.
In the cloud the API (Cloud Run) and the worker (VM) share no disk, so the raw zip goes to a
bucket (``gs://...`` in ``Task.storage_path``) and every reader extracts it into a local cache.
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Protocol

from ..taskspec import TASK_FILE, TaskSpec, TaskSpecError

MAX_FILES = 2000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
CHUNK = 64 * 1024
# The objective is stored in the database, returned in every task list and re-sent on every LLM
# call of an adversary run; real ones are a few KB.
MAX_OBJECTIVE_CHARS = 20_000


class BundleError(ValueError):
    """The uploaded bundle is unsafe or malformed."""


def _safe_member(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
        raise BundleError(f"unsafe path in archive: {name!r}")
    return p


def extract_bundle(data: bytes, dest: Path) -> Path:
    """Extract a zip into ``dest`` and return the directory that contains task.yaml."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BundleError("upload is not a valid .zip file") from exc

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES:
            raise BundleError(f"archive has more than {MAX_FILES} entries")
        dest.mkdir(parents=True, exist_ok=False)
        total = 0
        try:
            for info in infos:
                rel = _safe_member(info.filename)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise BundleError(f"symlinks are not allowed: {info.filename!r}")
                target = dest.joinpath(*rel.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                # Count real decompressed bytes; the sizes in the header can lie.
                with zf.open(info) as src, open(target, "wb") as out:
                    while chunk := src.read(CHUNK):
                        total += len(chunk)
                        if total > MAX_UNCOMPRESSED_BYTES:
                            raise BundleError("archive expands to more than 100 MB")
                        out.write(chunk)
        except (BundleError, zipfile.BadZipFile, OSError) as exc:
            shutil.rmtree(dest, ignore_errors=True)
            if isinstance(exc, BundleError):
                raise
            raise BundleError(f"could not extract archive: {exc}") from exc

    root = _find_root(dest)
    if root is None:
        shutil.rmtree(dest, ignore_errors=True)
        raise BundleError(f"no {TASK_FILE} at the top of the archive (or in a single top-level folder)")
    return root


def _find_root(dest: Path) -> Path | None:
    if (dest / TASK_FILE).is_file():
        return dest
    children = [c for c in dest.iterdir() if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / TASK_FILE).is_file():
        return children[0]
    return None


def _accept(spec: TaskSpec) -> TaskSpec:
    """Policy for uploaded (untrusted) tasks."""
    if spec.environment.network != "none":
        raise BundleError("uploaded tasks can't request network access (environment.network must be 'none')")
    if len(spec.objective) > MAX_OBJECTIVE_CHARS:
        raise BundleError(f"the objective is longer than {MAX_OBJECTIVE_CHARS} characters")
    return spec


class BlobBackend(Protocol):
    """Minimal object store: GCS in production, a dict in tests."""

    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class GCSBlobs:
    def __init__(self, bucket: str):
        from google.cloud import storage  # optional dependency (extra: gcs)

        self._bucket = storage.Client().bucket(bucket)

    def put(self, key: str, data: bytes) -> None:
        self._bucket.blob(key).upload_from_string(data, content_type="application/zip")

    def get(self, key: str) -> bytes:
        from google.api_core.exceptions import NotFound

        try:
            return self._bucket.blob(key).download_as_bytes()
        except NotFound:
            raise BundleError(f"task bundle {key!r} is missing from the bucket") from None


class MemoryBlobs:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise BundleError(f"task bundle {key!r} is missing from the bucket")
        return self.objects[key]


class TaskFiles:
    """Stores uploaded bundles and turns ``Task.storage_path`` back into a local folder.

    Without ``bucket`` bundles are extracted under ``local_dir`` and ``storage_path`` is that
    folder (dev). With ``bucket`` the zip is stored at ``gs://<bucket>/tasks/<org>/<task>.zip``
    and ``local_dir`` is only an extraction cache (bundles are immutable, so it never goes stale).
    """

    def __init__(self, local_dir: Path, bucket: str | None = None, blobs: BlobBackend | None = None):
        self.local_dir = local_dir
        self.bucket = bucket
        self._blobs = blobs
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        if bucket and blobs is None:
            self._blobs = GCSBlobs(bucket)

    def save(self, org_id: str, task_id: str, data: bytes) -> tuple[str, TaskSpec]:
        """Validate and store a bundle; returns (storage_path, parsed spec).
        Raises ``BundleError`` / ``TaskSpecError`` with server paths replaced by ``<bundle>``."""
        if not self.bucket:
            dest = self.local_dir / org_id / task_id
            try:
                root = extract_bundle(data, dest)
                return str(root), _accept(TaskSpec.load(root))
            except (BundleError, TaskSpecError) as exc:
                shutil.rmtree(dest, ignore_errors=True)
                raise type(exc)(str(exc).replace(str(dest), "<bundle>")) from None
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "b"
            try:
                spec = _accept(TaskSpec.load(extract_bundle(data, dest)))
            except (BundleError, TaskSpecError) as exc:
                raise type(exc)(str(exc).replace(str(dest), "<bundle>")) from None
        key = f"tasks/{org_id}/{task_id}.zip"
        self._blobs.put(key, data)
        return f"gs://{self.bucket}/{key}", spec

    def open(self, storage_path: str) -> Path:
        """Local folder containing task.yaml for a stored task (downloads on first use)."""
        if not storage_path.startswith("gs://"):
            return Path(storage_path)
        bucket, _, key = storage_path.removeprefix("gs://").partition("/")
        if bucket != self.bucket or not key.endswith(".zip"):
            raise BundleError(f"task bundle {storage_path!r} is not in the configured bucket")
        dest = self.local_dir.joinpath(*PurePosixPath(key.removesuffix(".zip")).parts)
        with self._lock_for(key):  # one download per bundle per process (API thread pool)
            if dest.is_dir() and (root := _find_root(dest)) is not None:
                return root
            # Extract into a private temp dir, then rename into place. The rename is atomic, so
            # `dest` is only ever absent or complete, even across processes or after a crash.
            tmp = dest.with_name(f"{dest.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
            try:
                root = extract_bundle(self._blobs.get(key), tmp)
                rel = root.relative_to(tmp)
                try:
                    tmp.rename(dest)
                except OSError:
                    if not dest.is_dir():  # not "another process won the race"
                        raise
                return dest / rel
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())
