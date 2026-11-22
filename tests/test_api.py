"""Backend tests: SQLite in memory + in-memory trace store. No Docker, no network."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")

from api_helpers import (  # noqa: E402
    PASSWORD,
    TASK_DIR,
    fake_report,
    make_org,
    register,
    upload,
    zip_dir,
    zip_entries,
)

from rewardhacker.api import jobs  # noqa: E402
from rewardhacker.api.db import normalize_url  # noqa: E402
from rewardhacker.api.storage import BundleError, MemoryBlobs, TaskFiles, extract_bundle  # noqa: E402
from rewardhacker.api.tables import Run, utcnow  # noqa: E402
from rewardhacker.api.traces import MemoryTraceStore  # noqa: E402

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


def test_bucket_task_files_round_trip(tmp_path):
    """Cloud layout: the API stores the zip in a bucket; the worker extracts it into its cache."""
    from rewardhacker.taskspec import TaskSpec, TaskSpecError

    blobs = MemoryBlobs()
    api = TaskFiles(tmp_path / "api", bucket="b", blobs=blobs)
    path, spec = api.save("org1", "task1", zip_dir(TASK_DIR, prefix="weak-output-check/"))
    assert path == "gs://b/tasks/org1/task1.zip" and spec.id == "weak-output-check"
    assert list(blobs.objects) == ["tasks/org1/task1.zip"]
    assert not (tmp_path / "api").exists()  # validation used a temp dir only

    worker = TaskFiles(tmp_path / "worker", bucket="b", blobs=blobs)
    root = worker.open(path)
    assert TaskSpec.load(root).id == "weak-output-check"
    blobs.objects.clear()
    assert worker.open(path) == root  # served from the cache, no download

    with pytest.raises(BundleError, match="configured bucket"):
        worker.open("gs://other/tasks/org1/task1.zip")
    with pytest.raises(TaskSpecError, match="verifier") as err:
        api.save("org1", "task2", zip_entries({"task.yaml": b"id: x\n"}))
    assert str(err.value).startswith("<bundle>")  # no server temp path leaks to the client


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


def test_serves_dashboard_with_spa_fallback(tmp_path):
    from fastapi.testclient import TestClient

    from rewardhacker.api.app import create_app
    from rewardhacker.api.db import Base, make_engine
    from rewardhacker.api.settings import ApiSettings

    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>app</html>")
    (web / "assets" / "main-abc.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = ApiSettings(database_url="sqlite://", jwt_secret="x" * 40, web_dir=web)
    client = TestClient(create_app(settings, engine=engine, traces=MemoryTraceStore()))

    assert client.get("/").text == "<html>app</html>"
    assert client.get("/runs/abc").text == "<html>app</html>"  # client-side route
    js = client.get("/assets/main-abc.js")
    assert js.text == "console.log(1)" and "immutable" in js.headers["cache-control"]
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/nope").status_code == 404
    assert client.get("/api/nope").headers["content-type"].startswith("application/json")
    assert "nope" not in client.get("/../secret.txt").text


# --- on-demand worker dispatch (Cloud Build) -------------------------------------------------


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeBuildApi:
    def __init__(self, statuses):
        self.statuses, self.created = list(statuses), []

    def get(self, url, params=None, timeout=None):
        assert params["filter"] == 'tags="rh-worker"'
        return _FakeResp({"builds": [{"status": s} for s in self.statuses]})

    def post(self, url, json=None, timeout=None):
        self.created.append(json)
        self.statuses.append("QUEUED")
        return _FakeResp({"metadata": {"build": {"id": f"b{len(self.created)}"}}})


def _dispatcher(api, **kw):
    from rewardhacker.api.dispatch import CloudBuildDispatcher

    return CloudBuildDispatcher(
        project="p",
        region="us-central1",
        image="img",
        service_account="w@p.iam.gserviceaccount.com",
        secrets={"DATABASE_URL": "database-url"},
        env={"RH_GCS_BUCKET": "b"},
        session=api,
        **kw,
    )


def test_dispatch_caps_concurrent_worker_builds():
    api = _FakeBuildApi(["SUCCESS", "WORKING"])
    d = _dispatcher(api, max_concurrent=2, min_interval_s=0)
    d.kick()  # 1 active -> start one
    d.kick()  # 2 active -> refuse
    assert len(api.created) == 1
    spec = api.created[0]
    step = spec["steps"][0]
    assert step["args"][:2] == ["worker", "--once"] and step["secretEnv"] == ["DATABASE_URL"]
    assert "RH_GCS_BUCKET=b" in step["env"] and spec["tags"] == ["rh-worker"]
    version = spec["availableSecrets"]["secretManager"][0]["versionName"]
    assert version.endswith("database-url/versions/latest")
    assert spec["serviceAccount"].endswith("w@p.iam.gserviceaccount.com")


def test_dispatch_throttles_and_never_raises():
    api = _FakeBuildApi([])
    d = _dispatcher(api, min_interval_s=60)
    d.kick()
    d.kick()  # throttled
    assert len(api.created) == 1

    class Broken:
        def get(self, *a, **k):
            raise ConnectionError("cloud build down")

    _dispatcher(Broken(), min_interval_s=0).kick()  # logged, not raised


def test_queueing_a_run_kicks_a_worker(env):
    client, sessions, _ = env
    kicks = []
    client.app.state.dispatcher.kick = lambda: kicks.append(1)
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()["id"]
    run = client.post(f"/api/orgs/{org}/tasks/{task}/runs", json={}, headers=h).json()
    assert kicks == [1]
    client.get(f"/api/orgs/{org}/runs/{run['id']}", headers=h)
    assert kicks == [1]  # fresh queued run: no re-kick
    with sessions() as db:
        db.get(Run, run["id"]).created_at = utcnow() - timedelta(minutes=5)
        db.commit()
    client.get(f"/api/orgs/{org}/runs/{run['id']}", headers=h)
    assert kicks == [1, 1]  # stuck in the queue: self-heal


# --- review fixes (2026-11-22) ----------------------------------------------------------------


def test_concurrent_open_of_uncached_bundle_is_safe(tmp_path):
    import threading

    from rewardhacker.taskspec import TaskSpec

    blobs = MemoryBlobs()
    path, _ = TaskFiles(tmp_path / "api", bucket="b", blobs=blobs).save("o", "t", zip_dir(TASK_DIR))
    # Separate TaskFiles objects = separate processes (no shared lock); one = one process's threads.
    shared = TaskFiles(tmp_path / "cache", bucket="b", blobs=blobs)
    stores = [shared] * 4 + [TaskFiles(tmp_path / "cache", bucket="b", blobs=blobs) for _ in range(4)]
    roots, errors = [], []

    def go(store):
        try:
            roots.append(store.open(path))
        except Exception as exc:  # pragma: no cover - the assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(s,)) for s in stores]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(set(roots)) == 1
    assert TaskSpec.load(roots[0]).id == "weak-output-check"
    assert not [p for p in (tmp_path / "cache" / "tasks" / "o").iterdir() if ".tmp-" in p.name]


def test_missing_bundle_is_a_422_not_a_500(env):
    client, sessions, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()["id"]
    from rewardhacker.api.tables import Task

    with sessions() as db:
        db.get(Task, task).storage_path = "gs://other-bucket/tasks/x.zip"
        db.commit()
    r = client.post(f"/api/orgs/{org}/tasks/{task}/spec-checks", headers=h)
    assert r.status_code == 422 and "bucket" in r.text


def test_stuck_running_run_and_run_lists_kick_a_worker(env):
    client, sessions, _ = env
    kicks = []
    client.app.state.dispatcher.kick = lambda: kicks.append(1)
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()["id"]
    run = client.post(f"/api/orgs/{org}/tasks/{task}/runs", json={}, headers=h).json()
    kicks.clear()
    with sessions() as db:
        r = db.get(Run, run["id"])
        r.status, r.started_at = "running", utcnow() - timedelta(minutes=10)
        db.commit()
    client.get(f"/api/orgs/{org}/runs", headers=h)
    assert kicks == []  # running normally
    with sessions() as db:
        db.get(Run, run["id"]).started_at = utcnow() - jobs.STALE_AFTER - timedelta(minutes=1)
        db.commit()
    client.get(f"/api/orgs/{org}/runs", headers=h)  # the list view self-heals too
    assert kicks == [1]
    assert jobs.STALE_AFTER.total_seconds() > 1800  # longer than a worker build's timeout


def test_ai_features_need_per_org_approval_on_public_deployment(tmp_path):
    """Public deployment (RH_NEW_ORGS_LLM=0): new orgs get free static probes only; paid AI
    endpoints return 403 until the operator enables the org."""
    from api_helpers import SpecLLM
    from fastapi.testclient import TestClient

    from rewardhacker.api.app import create_app
    from rewardhacker.api.db import Base, make_engine, make_sessionmaker
    from rewardhacker.api.rag import HashEmbedder, MemoryGuidelineIndex
    from rewardhacker.api.settings import ApiSettings
    from rewardhacker.api.tables import Org

    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = ApiSettings(
        database_url="sqlite://", jwt_secret="x" * 40, storage_dir=tmp_path / "s", new_orgs_llm=False
    )
    client = TestClient(
        create_app(
            settings,
            engine=engine,
            traces=MemoryTraceStore(),
            guideline_index=MemoryGuidelineIndex(),
            embedder=HashEmbedder(),
            llm_factory=lambda: SpecLLM(),
        )
    )
    h = register(client, "a@x.io")
    org = client.post("/api/orgs", json={"name": "Stranger"}, headers=h).json()
    assert org["llm_enabled"] is False
    task = upload(client, org["id"], h, zip_dir(TASK_DIR)).json()["id"]
    base = f"/api/orgs/{org['id']}"

    assert client.post(f"{base}/tasks/{task}/runs", json={"include_llm": False}, headers=h).status_code == 202
    r = client.post(f"{base}/tasks/{task}/runs", json={"include_llm": True}, headers=h)
    assert r.status_code == 403 and "not enabled" in r.text
    guideline = {"title": "G", "content": "# A\ntext"}
    assert client.post(f"{base}/guidelines", json=guideline, headers=h).status_code == 403
    assert client.post(f"{base}/tasks/{task}/spec-checks", headers=h).status_code == 403

    with make_sessionmaker(engine)() as db:
        db.get(Org, org["id"]).llm_enabled = True
        db.commit()
    assert client.get("/api/auth/me", headers=h).json()["orgs"][0]["llm_enabled"] is True
    assert client.post(f"{base}/tasks/{task}/runs", json={"include_llm": True}, headers=h).status_code == 202


def test_workers_get_the_same_llm_caps_as_the_api(monkeypatch):
    from rewardhacker.api.dispatch import dispatcher_from_env

    for k, v in {
        "RH_WORKER_IMAGE": "img",
        "RH_GCP_PROJECT": "p",
        "RH_WORKER_SERVICE_ACCOUNT": "w@p",
        "RH_DAILY_BUDGET_USD": "0.10",
        "RH_GCS_BUCKET": "b",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("RH_RUN_BUDGET_USD", raising=False)
    env = dispatcher_from_env().build_spec()["steps"][0]["env"]
    assert "RH_DAILY_BUDGET_USD=0.10" in env and "RH_GCS_BUCKET=b" in env
    assert not any(e.startswith("RH_RUN_BUDGET_USD=") for e in env)  # unset → worker default
