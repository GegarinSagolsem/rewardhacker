"""FastAPI application factory.

Run locally:  uv run rh serve   (or: uvicorn rewardhacker.api.app:create_app --factory)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import Engine

from .. import __version__
from ..config import get_settings
from ..llm import LLM, default_ledger, default_llm
from .db import make_engine, make_sessionmaker
from .dispatch import Dispatcher, dispatcher_from_env
from .exports import ExportStore, GCSExportStore, LocalExportStore
from .rag import Embedder, GeminiEmbedder, GuidelineIndex, MemoryGuidelineIndex, MongoGuidelineIndex
from .routes import apikeys, audit, auth, exports, guidelines, orgs, runs, tasks
from .settings import ApiSettings, get_api_settings
from .storage import TaskFiles
from .traces import TraceStore, make_trace_store


def _default_embedder() -> Embedder | None:
    s = get_settings()
    if s.llm_disabled or not s.gemini_api_key:
        return None
    return GeminiEmbedder(s.gemini_api_key, default_ledger(s.daily_budget_usd))


def create_app(
    settings: ApiSettings | None = None,
    engine: Engine | None = None,
    traces: TraceStore | None = None,
    export_store: ExportStore | None = None,
    guideline_index: GuidelineIndex | None = None,
    embedder: Embedder | None = None,
    llm_factory: Callable[[], LLM | None] | None = None,
    task_files: TaskFiles | None = None,
    dispatcher: Dispatcher | None = None,
) -> FastAPI:
    """Build the app. Every external dependency can be injected (tests pass fakes)."""
    settings = settings or get_api_settings()
    engine = engine or make_engine(settings.database_url)

    app = FastAPI(
        title="RewardHacker API",
        version=__version__,
        description="Red-team your rewards: probe RL coding tasks for loopholes.",
    )
    app.state.settings = settings
    app.state.dispatcher = dispatcher or dispatcher_from_env()
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.traces = traces or make_trace_store(settings.mongodb_uri, settings.mongodb_db)
    if export_store is None:
        export_store = (
            GCSExportStore(settings.gcs_bucket)
            if settings.gcs_bucket
            else LocalExportStore(settings.exports_dir, settings.jwt_secret)
        )
    app.state.exports = export_store
    app.state.task_files = task_files or TaskFiles(settings.storage_dir, settings.gcs_bucket)
    if guideline_index is None:
        guideline_index = (
            MongoGuidelineIndex(settings.mongodb_uri, settings.mongodb_db)
            if settings.mongodb_uri
            else MemoryGuidelineIndex()
        )
    app.state.guidelines = guideline_index
    app.state.embedder = embedder if embedder is not None else _default_embedder()
    app.state.llm_factory = llm_factory or default_llm

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for module in (auth, orgs, tasks, runs, exports, guidelines, apikeys, audit):
        app.include_router(module.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    if settings.web_dir is not None:
        _serve_web(app, settings.web_dir)
    return app


def _serve_web(app: FastAPI, web_dir: Path) -> None:
    """Serve the built dashboard. Unknown non-API paths get index.html (client-side routing);
    unknown /api paths keep returning JSON 404s."""
    root = web_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"RH_WEB_DIR={web_dir} has no index.html (run `npm run build` in web/)")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            # Vite fingerprints everything under assets/, so it can be cached forever.
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
