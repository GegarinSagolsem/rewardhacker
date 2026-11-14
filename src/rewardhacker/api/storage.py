"""Safe extraction of uploaded task bundles (.zip).

Uploads are untrusted: refuse path traversal ("zip slip"), absolute paths, symlinks, zip bombs
and absurd file counts. Local disk for now; GCS on day 9.
"""

from __future__ import annotations

import io
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from ..taskspec import TASK_FILE

MAX_FILES = 2000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
CHUNK = 64 * 1024


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

    if (dest / TASK_FILE).is_file():
        return dest
    children = [c for c in dest.iterdir() if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / TASK_FILE).is_file():
        return children[0]
    shutil.rmtree(dest, ignore_errors=True)
    raise BundleError(f"no {TASK_FILE} at the top of the archive (or in a single top-level folder)")
