"""Shared fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def env(tmp_path):
    """API test app: in-memory SQLite and fakes for every external service. Returns
    (client, sessionmaker, trace store)."""
    pytest.importorskip("fastapi")
    from api_helpers import SpecLLM
    from fastapi.testclient import TestClient

    from rewardhacker.api.app import create_app
    from rewardhacker.api.db import Base, make_engine, make_sessionmaker
    from rewardhacker.api.exports import LocalExportStore
    from rewardhacker.api.rag import HashEmbedder, MemoryGuidelineIndex
    from rewardhacker.api.settings import ApiSettings
    from rewardhacker.api.traces import MemoryTraceStore

    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = ApiSettings(
        database_url="sqlite://",
        jwt_secret="x" * 40,
        storage_dir=tmp_path / "store",
        exports_dir=tmp_path / "exports",
    )
    traces = MemoryTraceStore()
    llm = SpecLLM()
    app = create_app(
        settings,
        engine=engine,
        traces=traces,
        export_store=LocalExportStore(settings.exports_dir, settings.jwt_secret),
        guideline_index=MemoryGuidelineIndex(),
        embedder=HashEmbedder(),
        llm_factory=lambda: llm,
    )
    return TestClient(app), make_sessionmaker(engine), traces
