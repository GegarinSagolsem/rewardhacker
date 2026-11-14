"""FastAPI application factory.

Run locally:  uv run rh serve   (or: uvicorn rewardhacker.api.app:create_app --factory)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from .. import __version__
from .db import make_engine, make_sessionmaker
from .routes import auth, orgs, runs, tasks
from .settings import ApiSettings, get_api_settings
from .traces import TraceStore, make_trace_store


def create_app(
    settings: ApiSettings | None = None,
    engine: Engine | None = None,
    traces: TraceStore | None = None,
) -> FastAPI:
    settings = settings or get_api_settings()
    engine = engine or make_engine(settings.database_url)

    app = FastAPI(
        title="RewardHacker API",
        version=__version__,
        description="Red-team your rewards: probe RL coding tasks for loopholes.",
    )
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.traces = traces or make_trace_store(settings.mongodb_uri, settings.mongodb_db)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for module in (auth, orgs, tasks, runs):
        app.include_router(module.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app
