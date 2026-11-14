from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Principal, get_db, require_role
from ..exports import EXPORT_KINDS, ExportError, LocalExportStore, build_export
from ..schemas import ExportCreate, ExportLink, ExportOut
from ..tables import Export, Role

router = APIRouter(tags=["exports"])
reviewer = require_role(Role.REVIEWER)


def _link(request: Request, export: Export) -> ExportLink:
    url, expires = request.app.state.exports.link(export)
    return ExportLink(**ExportOut.model_validate(export).model_dump(), url=url, url_expires_at=expires)


@router.post("/api/orgs/{org_id}/exports", response_model=ExportLink, status_code=status.HTTP_201_CREATED)
def create_export(
    org_id: str,
    body: ExportCreate,
    request: Request,
    actor: Principal = Depends(reviewer),
    db: Session = Depends(get_db),
) -> ExportLink:
    """Build an export file and return a download link valid for 15 minutes."""
    try:
        data, filename, rows = build_export(db, org_id, body.kind, body.run_id, request.app.state.traces)
    except ExportError as exc:
        code = status.HTTP_404_NOT_FOUND if "not found" in str(exc) else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, str(exc)) from None
    export = Export(
        org_id=org_id,
        kind=body.kind,
        run_id=body.run_id if body.kind.startswith("report.") else None,
        filename=filename,
        content_type=EXPORT_KINDS[body.kind][0],
        size_bytes=len(data),
        row_count=rows,
        created_by_label=actor.label,
        object_key="",
    )
    db.add(export)
    db.flush()
    export.object_key = f"exports/{org_id}/{export.id}/{filename}"
    request.app.state.exports.put(export.object_key, data, export.content_type)
    actor.audit(db, "export.create", "export", export.id, kind=body.kind, rows=rows, run_id=body.run_id)
    db.commit()
    return _link(request, export)


@router.get("/api/orgs/{org_id}/exports", response_model=list[ExportOut])
def list_exports(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    _: Principal = Depends(reviewer),
    db: Session = Depends(get_db),
) -> list[Export]:
    stmt = select(Export).where(Export.org_id == org_id).order_by(Export.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


@router.post("/api/orgs/{org_id}/exports/{export_id}/link", response_model=ExportLink)
def refresh_link(
    org_id: str,
    export_id: str,
    request: Request,
    _: Principal = Depends(reviewer),
    db: Session = Depends(get_db),
) -> ExportLink:
    export = db.get(Export, export_id)
    if export is None or export.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export not found")
    return _link(request, export)


@router.get("/api/exports/{export_id}/download", include_in_schema=False)
def download(
    export_id: str, expires: int, sig: str, request: Request, db: Session = Depends(get_db)
) -> FileResponse:
    """Serve a local export. The HMAC-signed, expiring link is the authorization."""
    store = request.app.state.exports
    if not isinstance(store, LocalExportStore) or not store.verify(export_id, expires, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "link is invalid or expired")
    export = db.get(Export, export_id)
    if export is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export not found")
    return FileResponse(
        store.path(export.object_key), media_type=export.content_type, filename=export.filename
    )
