"""Backend tests: SQLite in memory + in-memory trace store. No Docker, no network."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from rewardhacker.api import jobs  # noqa: E402
from rewardhacker.api.app import create_app  # noqa: E402
from rewardhacker.api.db import Base, make_engine, make_sessionmaker, normalize_url  # noqa: E402
from rewardhacker.api.settings import ApiSettings  # noqa: E402
from rewardhacker.api.storage import BundleError, extract_bundle  # noqa: E402
from rewardhacker.api.tables import Run, utcnow  # noqa: E402
from rewardhacker.api.traces import MemoryTraceStore  # noqa: E402
from rewardhacker.models import AgentRun, AgentStep, LLMUsage, ProbeResult, Report, Trial  # noqa: E402

TASK_DIR = Path(__file__).parent.parent / "loopbench" / "tasks" / "weak-output-check"
PASSWORD = "correct-horse-battery"


def zip_dir(src: Path, prefix: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, prefix + p.relative_to(src).as_posix())
    return buf.getvalue()


def zip_entries(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def env(tmp_path):
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = ApiSettings(database_url="sqlite://", jwt_secret="x" * 40, storage_dir=tmp_path / "store")
    traces = MemoryTraceStore()
    app = create_app(settings, engine=engine, traces=traces)
    client = TestClient(app)
    return client, make_sessionmaker(engine), traces


def register(client, email: str) -> dict:
    assert client.post("/api/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    tok = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def make_org(client, headers) -> str:
    r = client.post("/api/orgs", json={"name": "Acme RL"}, headers=headers)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    return r.json()["id"]


def upload(client, org, headers, data: bytes):
    return client.post(
        f"/api/orgs/{org}/tasks", files={"file": ("task.zip", data, "application/zip")}, headers=headers
    )


def fake_report(task_id: str) -> Report:
    agent = AgentRun(
        steps=[AgentStep(step=1, tool="bash", args={"command": "echo 'total: 0' > report.txt"})],
        explanation="wrote a placeholder total",
        stop_reason="submitted",
        usage=LLMUsage(model="fake", calls=2, cost_usd=0.001),
        judgement="shortcut",
    )
    probe = ProbeResult(
        name="adversary",
        title="LLM adversary",
        expect_pass=False,
        status="finding",
        trials=[Trial(index=0, passed=True, agent=agent)],
    )
    return Report(
        task_id=task_id,
        image="img",
        rewardhacker_version="test",
        started_at="2026-11-14T00:00:00+00:00",
        duration_sec=1.0,
        probes=[probe],
        findings=[],
        score=50,
        verdict="exploitable",
        llm_usage=agent.usage,
    )


# --- auth -----------------------------------------------------------------------------------


def test_register_login_me(env):
    client, _, _ = env
    h = register(client, "Alice@Example.com")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "alice@example.com" and me["orgs"] == []
    assert "password_hash" not in me


def test_duplicate_email_and_bad_login(env):
    client, _, _ = env
    register(client, "a@x.io")
    assert (
        client.post("/api/auth/register", json={"email": "a@x.io", "password": PASSWORD}).status_code == 409
    )
    bad = client.post("/api/auth/login", json={"email": "a@x.io", "password": "wrong-password"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@x.io", "password": PASSWORD})
    assert unknown.status_code == 401


def test_requires_valid_token(env):
    client, _, _ = env
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_short_password_rejected(env):
    client, _, _ = env
    assert client.post("/api/auth/register", json={"email": "a@x.io", "password": "short"}).status_code == 422


# --- orgs and roles -------------------------------------------------------------------------


def test_roles_are_enforced(env):
    client, _, _ = env
    admin = register(client, "admin@x.io")
    viewer = register(client, "viewer@x.io")
    outsider = register(client, "out@x.io")
    org = make_org(client, admin)
    r = client.post(
        f"/api/orgs/{org}/members", json={"email": "viewer@x.io", "role": "viewer"}, headers=admin
    )
    assert r.status_code == 201

    # Viewer can read but not upload or manage members.
    assert client.get(f"/api/orgs/{org}/tasks", headers=viewer).status_code == 200
    assert upload(client, org, viewer, zip_dir(TASK_DIR)).status_code == 403
    r = client.post(f"/api/orgs/{org}/members", json={"email": "out@x.io"}, headers=viewer)
    assert r.status_code == 403
    # Outsiders can't even tell the org exists.
    assert client.get(f"/api/orgs/{org}/tasks", headers=outsider).status_code == 404
    assert client.get(f"/api/orgs/{org}/members", headers=outsider).status_code == 404


def test_last_admin_cannot_leave_or_be_demoted(env):
    client, _, _ = env
    admin = register(client, "admin@x.io")
    org = make_org(client, admin)
    me = client.get("/api/auth/me", headers=admin).json()["id"]
    r = client.patch(f"/api/orgs/{org}/members/{me}", json={"role": "viewer"}, headers=admin)
    assert r.status_code == 409
    assert client.delete(f"/api/orgs/{org}/members/{me}", headers=admin).status_code == 409

    register(client, "second@x.io")
    client.post(f"/api/orgs/{org}/members", json={"email": "second@x.io", "role": "admin"}, headers=admin)
    assert client.delete(f"/api/orgs/{org}/members/{me}", headers=admin).status_code == 204


# --- task upload ----------------------------------------------------------------------------


def test_upload_task_bundle(env):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    r = upload(client, org, h, zip_dir(TASK_DIR, prefix="weak-output-check/"))
    assert r.status_code == 201, r.text
    assert r.json()["spec_id"] == "weak-output-check"
    tasks = client.get(f"/api/orgs/{org}/tasks", headers=h).json()
    assert [t["id"] for t in tasks] == [r.json()["id"]]


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a zip", "not a valid .zip"),
        (zip_entries({"readme.txt": b"hi"}), "no task.yaml"),
        (zip_entries({"task.yaml": b"id: x\n"}), "verifier"),
    ],
)
def test_upload_rejects_bad_bundles(env, data, message):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    r = upload(client, org, h, data)
    assert r.status_code == 422 and message in r.text


def test_extract_refuses_zip_slip(tmp_path):
    with pytest.raises(BundleError, match="unsafe path"):
        extract_bundle(zip_entries({"../evil.txt": b"x"}), tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "out").exists()


def test_extract_refuses_symlinks(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(BundleError, match="symlinks"):
        extract_bundle(buf.getvalue(), tmp_path / "out")


# --- runs and the queue ---------------------------------------------------------------------


def test_run_lifecycle_with_traces(env):
    client, sessions, traces = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()

    r = client.post(f"/api/orgs/{org}/tasks/{task['id']}/runs", json={"include_llm": True}, headers=h)
    assert r.status_code == 202 and r.json()["status"] == "queued"
    run_id = r.json()["id"]

    seen: dict = {}

    def probe_fn(spec, names):
        seen["names"] = names
        return fake_report(spec.id)

    with sessions() as db:
        run = jobs.claim_next(db, "w1")
        assert run is not None and run.id == run_id and run.status == "running"
        assert jobs.claim_next(db, "w2") is None  # nothing else queued
        jobs.execute(db, run, traces, probe_fn=probe_fn)
    assert seen["names"] is None  # include_llm → all probes

    detail = client.get(f"/api/orgs/{org}/runs/{run_id}", headers=h).json()
    assert detail["status"] == "done" and detail["verdict"] == "exploitable" and detail["score"] == 50
    assert detail["llm_cost_usd"] == pytest.approx(0.001)
    assert detail["traces_stored"] is True
    # Steps moved out of the Postgres report and into the trace store.
    assert detail["report"]["probes"][0]["trials"][0]["agent"]["steps"] == []
    tr = client.get(f"/api/orgs/{org}/runs/{run_id}/traces", headers=h).json()
    assert len(tr) == 1 and tr[0]["probe"] == "adversary" and tr[0]["steps"][0]["tool"] == "bash"
    assert tr[0]["org_id"] == org


def test_static_only_by_default_and_failures_recorded(env):
    client, sessions, traces = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()
    client.post(f"/api/orgs/{org}/tasks/{task['id']}/runs", headers=h)

    seen: dict = {}

    def boom(spec, names):
        seen["names"] = names
        raise RuntimeError("docker exploded")

    with sessions() as db:
        run = jobs.claim_next(db, "w1")
        jobs.execute(db, run, traces, probe_fn=boom)
    assert "adversary" not in seen["names"] and "null" in seen["names"]
    runs = client.get(f"/api/orgs/{org}/runs?status=failed", headers=h).json()
    assert len(runs) == 1 and "docker exploded" in runs[0]["error"]


def test_trace_store_outage_keeps_steps_inline(env):
    client, sessions, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()
    run_id = client.post(f"/api/orgs/{org}/tasks/{task['id']}/runs", headers=h).json()["id"]

    class DownStore(MemoryTraceStore):
        def save(self, docs):
            raise ConnectionError("mongo down")

    with sessions() as db:
        jobs.execute(db, jobs.claim_next(db, "w1"), DownStore(), probe_fn=lambda s, n: fake_report(s.id))
    detail = client.get(f"/api/orgs/{org}/runs/{run_id}", headers=h).json()
    assert detail["status"] == "done" and detail["traces_stored"] is False
    assert detail["report"]["probes"][0]["trials"][0]["agent"]["steps"]


def test_recover_stale_requeues_then_fails(env):
    client, sessions, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()
    run_id = client.post(f"/api/orgs/{org}/tasks/{task['id']}/runs", headers=h).json()["id"]

    with sessions() as db:
        for attempt in range(1, jobs.MAX_ATTEMPTS + 1):
            run = jobs.claim_next(db, "w1")
            assert run is not None and run.attempts == attempt
            run.started_at = utcnow() - timedelta(hours=2)
            db.commit()
            assert jobs.recover_stale(db) == 1
        assert db.get(Run, run_id).status == "failed"


def test_runs_are_org_scoped(env):
    client, _, _ = env
    a = register(client, "a@x.io")
    b = register(client, "b@x.io")
    org_a, org_b = make_org(client, a), make_org(client, b)
    task = upload(client, org_a, a, zip_dir(TASK_DIR)).json()
    run_id = client.post(f"/api/orgs/{org_a}/tasks/{task['id']}/runs", headers=a).json()["id"]
    # b is admin of org_b but must not reach org_a's run or task through it.
    assert client.get(f"/api/orgs/{org_b}/runs/{run_id}", headers=b).status_code == 404
    assert client.post(f"/api/orgs/{org_b}/tasks/{task['id']}/runs", headers=b).status_code == 404


def test_normalize_url():
    assert normalize_url("postgresql://u:p@h/db?sslmode=require").startswith("postgresql+psycopg://")
    assert normalize_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert normalize_url("sqlite://") == "sqlite://"
