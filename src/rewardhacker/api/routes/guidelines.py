from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...llm import BudgetExceeded
from ...taskspec import TaskSpec, TaskSpecError
from ..deps import Principal, get_db, require_role
from ..rag import chunk_markdown, run_spec_check
from ..schemas import GuidelineCreate, GuidelineDetail, GuidelineOut, SpecCheckOut
from ..tables import Guideline, Role, SpecCheck
from .tasks import get_task

router = APIRouter(prefix="/api/orgs/{org_id}", tags=["guidelines"])
admin_only = require_role(Role.ADMIN, allow_api_key=False)


def _need_llm(request: Request):
    embedder, llm = request.app.state.embedder, request.app.state.llm_factory()
    if embedder is None or llm is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "no LLM configured (set GEMINI_API_KEY)")
    return embedder, llm


@router.get("/guidelines", response_model=list[GuidelineOut])
def list_guidelines(
    org_id: str, _: Principal = Depends(require_role(Role.VIEWER)), db: Session = Depends(get_db)
) -> list[Guideline]:
    stmt = select(Guideline).where(Guideline.org_id == org_id).order_by(Guideline.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/guidelines/{guideline_id}", response_model=GuidelineDetail)
def read_guideline(
    org_id: str,
    guideline_id: str,
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Guideline:
    g = db.get(Guideline, guideline_id)
    if g is None or g.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guideline not found")
    return g


@router.post("/guidelines", response_model=GuidelineOut, status_code=status.HTTP_201_CREATED)
def add_guideline(
    org_id: str,
    body: GuidelineCreate,
    request: Request,
    actor: Principal = Depends(admin_only),
    db: Session = Depends(get_db),
) -> Guideline:
    """Add a Markdown guideline document. It is chunked by heading and embedded for retrieval."""
    embedder = request.app.state.embedder
    if embedder is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "no embedding model configured (set GEMINI_API_KEY)"
        )
    chunks = chunk_markdown(body.content)
    if not chunks:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "the document has no text")
    try:
        texts = [f"{body.title}\n{c.heading}\n{c.text}" for c in chunks]
        vectors, cost = embedder.embed(texts, "document")
    except BudgetExceeded as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from None
    g = Guideline(
        org_id=org_id,
        title=body.title.strip(),
        content=body.content,
        chunk_count=len(chunks),
        created_by=actor.user_id,
    )
    db.add(g)
    db.flush()
    request.app.state.guidelines.add(org_id, g.id, g.title, chunks, vectors)
    actor.audit(
        db, "guideline.add", "guideline", g.id, title=g.title, chunks=len(chunks), cost_usd=round(cost, 6)
    )
    db.commit()
    return g


@router.delete("/guidelines/{guideline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guideline(
    org_id: str,
    guideline_id: str,
    request: Request,
    actor: Principal = Depends(admin_only),
    db: Session = Depends(get_db),
) -> Response:
    g = db.get(Guideline, guideline_id)
    if g is None or g.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guideline not found")
    request.app.state.guidelines.delete(g.id)
    actor.audit(db, "guideline.delete", "guideline", g.id, title=g.title)
    db.delete(g)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/spec-checks", response_model=SpecCheckOut, status_code=status.HTTP_201_CREATED)
def create_spec_check(
    org_id: str,
    task_id: str,
    request: Request,
    actor: Principal = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> SpecCheck:
    """Check the task against the org's guidelines (retrieval + one LLM call, ~$0.001)."""
    task = get_task(db, org_id, task_id)
    embedder, llm = _need_llm(request)
    try:
        spec = TaskSpec.load(request.app.state.task_files.open(task.storage_path))
        result = run_spec_check(spec, org_id, embedder, request.app.state.guidelines, llm)
    except TaskSpecError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except BudgetExceeded as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from None
    check = SpecCheck(
        org_id=org_id,
        task_id=task_id,
        created_by_label=actor.label,
        model=result.get("model") or getattr(llm, "model", ""),
        cost_usd=result.get("cost_usd", 0.0),
        result=result,
    )
    db.add(check)
    db.flush()
    actor.audit(
        db,
        "spec_check.run",
        "task",
        task_id,
        spec_id=task.spec_id,
        issues=len(result["issues"]),
        cost_usd=check.cost_usd,
    )
    db.commit()
    return check


@router.get("/tasks/{task_id}/spec-checks", response_model=list[SpecCheckOut])
def list_spec_checks(
    org_id: str,
    task_id: str,
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[SpecCheck]:
    get_task(db, org_id, task_id)
    stmt = (
        select(SpecCheck)
        .where(SpecCheck.org_id == org_id, SpecCheck.task_id == task_id)
        .order_by(SpecCheck.created_at.desc())
        .limit(10)
    )
    return list(db.scalars(stmt))
