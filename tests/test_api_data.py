"""Day-9 backend features: audit log, API keys, exports, guidelines + RAG spec check.

Same setup as test_api.py: SQLite, in-memory stores, scripted LLM, hash embedder. No network.
"""

from __future__ import annotations

import csv
import io
import json
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")

from api_helpers import TASK_DIR, fake_report, login, make_org, register, upload, zip_dir  # noqa: E402

from rewardhacker.api import jobs  # noqa: E402
from rewardhacker.api.rag import chunk_markdown  # noqa: E402

GUIDE = """\
# Task quality guidelines

## Verifiers
Tests must check the exact expected values, not just the output format or that a file exists.

## Determinism
The verifier must give the same answer for the same work. Avoid timing and randomness.

## Environment
Never give the agent network access.
"""


def _task_with_run(client, sessions, traces, h, org):
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()
    run_id = client.post(
        f"/api/orgs/{org}/tasks/{task['id']}/runs", json={"include_llm": True}, headers=h
    ).json()["id"]
    with sessions() as db:
        jobs.execute(db, jobs.claim_next(db, "w"), traces, probe_fn=lambda s, n: fake_report(s.id))
    return task, run_id


# --- audit log --------------------------------------------------------------------------------


def test_audit_log_records_actions_and_is_admin_only(env):
    client, sessions, traces = env
    admin = register(client, "admin@x.io")
    org = make_org(client, admin)
    register(client, "rev@x.io")
    client.post(f"/api/orgs/{org}/members", json={"email": "rev@x.io", "role": "reviewer"}, headers=admin)
    _task_with_run(client, sessions, traces, admin, org)

    events = client.get(f"/api/orgs/{org}/audit", headers=admin).json()
    actions = [e["action"] for e in events]
    assert actions == ["run.start", "task.upload", "member.add", "org.create"]  # newest first
    assert events[0]["actor_label"] == "admin@x.io"
    assert events[2]["data"] == {"email": "rev@x.io", "role": "reviewer"}
    only_members = client.get(f"/api/orgs/{org}/audit?action=member.", headers=admin).json()
    assert [e["action"] for e in only_members] == ["member.add"]

    assert client.get(f"/api/orgs/{org}/audit", headers=login(client, "rev@x.io")).status_code == 403


# --- API keys ---------------------------------------------------------------------------------


def test_api_key_lifecycle(env):
    client, _, _ = env
    admin = register(client, "admin@x.io")
    org = make_org(client, admin)
    other_org = make_org(client, admin)

    r = client.post(f"/api/orgs/{org}/api-keys", json={"name": "CI", "role": "reviewer"}, headers=admin)
    assert r.status_code == 201
    key = r.json()["key"]
    assert key.startswith("rh_") and r.json()["prefix"] == key[:10]
    listed = client.get(f"/api/orgs/{org}/api-keys", headers=admin).json()
    assert "key" not in listed[0] and "key_hash" not in listed[0]

    k = {"Authorization": f"Bearer {key}"}
    # A reviewer key can upload and start runs...
    task = upload(client, org, k, zip_dir(TASK_DIR))
    assert task.status_code == 201 and task.json()["uploaded_by"] is None
    assert client.post(f"/api/orgs/{org}/tasks/{task.json()['id']}/runs", headers=k).status_code == 202
    # ...but is bound to its org, can't manage people, and isn't a user session.
    assert client.get(f"/api/orgs/{other_org}/tasks", headers=k).status_code == 404
    assert client.get(f"/api/orgs/{org}/members", headers=k).status_code == 200
    assert client.post(f"/api/orgs/{org}/members", json={"email": "a@b.io"}, headers=k).status_code == 403
    assert client.get(f"/api/orgs/{org}/api-keys", headers=k).status_code == 403
    assert client.get("/api/auth/me", headers=k).status_code == 401

    labels = {e["actor_label"] for e in client.get(f"/api/orgs/{org}/audit", headers=admin).json()}
    assert "key: CI" in labels

    key_id = listed[0]["id"]
    assert client.delete(f"/api/orgs/{org}/api-keys/{key_id}", headers=admin).status_code == 204
    assert client.get(f"/api/orgs/{org}/tasks", headers=k).status_code == 401


def test_api_keys_cannot_be_admin(env):
    client, _, _ = env
    admin = register(client, "admin@x.io")
    org = make_org(client, admin)
    r = client.post(f"/api/orgs/{org}/api-keys", json={"name": "x", "role": "admin"}, headers=admin)
    assert r.status_code == 422


# --- exports ----------------------------------------------------------------------------------


def _download(client, url: str):
    return client.get(url)


def test_exports_csv_jsonl_and_report(env):
    client, sessions, traces = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    _, run_id = _task_with_run(client, sessions, traces, h, org)

    csv_link = client.post(f"/api/orgs/{org}/exports", json={"kind": "runs.csv"}, headers=h)
    assert csv_link.status_code == 201 and csv_link.json()["row_count"] == 1
    body = _download(client, csv_link.json()["url"])
    assert body.status_code == 200 and "attachment" in body.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(body.text)))
    assert (
        rows[0]["run_id"] == run_id
        and rows[0]["verdict"] == "exploitable"
        and rows[0]["task"] == "weak-output-check"
    )

    jl = client.post(f"/api/orgs/{org}/exports", json={"kind": "runs.jsonl"}, headers=h).json()
    line = json.loads(_download(client, jl["url"]).text.splitlines()[0])
    assert line["report"]["verdict"] == "exploitable"

    md = client.post(
        f"/api/orgs/{org}/exports", json={"kind": "report.md", "run_id": run_id}, headers=h
    ).json()
    text = _download(client, md["url"]).text
    assert "# RewardHacker report: `weak-output-check`" in text
    assert "$ echo 'total: 0' > report.txt" in text  # trace steps pulled back from the trace store

    js = client.post(
        f"/api/orgs/{org}/exports", json={"kind": "report.json", "run_id": run_id}, headers=h
    ).json()
    assert json.loads(_download(client, js["url"]).text)["adversary_traces"][0]["probe"] == "adversary"

    assert len(client.get(f"/api/orgs/{org}/exports", headers=h).json()) == 4


def test_export_links_are_signed_and_scoped(env):
    client, sessions, traces = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    _, run_id = _task_with_run(client, sessions, traces, h, org)
    url = client.post(f"/api/orgs/{org}/exports", json={"kind": "runs.csv"}, headers=h).json()["url"]
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    tampered = f"{parsed.path}?expires={int(q['expires'][0]) + 3600}&sig={q['sig'][0]}"
    assert client.get(tampered).status_code == 403
    expired = f"{parsed.path}?expires=1&sig={q['sig'][0]}"
    assert client.get(expired).status_code == 403

    # Bad requests
    assert client.post(f"/api/orgs/{org}/exports", json={"kind": "nope"}, headers=h).status_code == 422
    r = client.post(f"/api/orgs/{org}/exports", json={"kind": "report.md", "run_id": "missing"}, headers=h)
    assert r.status_code == 404
    # Another org can't export this org's run.
    b = register(client, "b@x.io")
    org_b = make_org(client, b)
    r = client.post(f"/api/orgs/{org_b}/exports", json={"kind": "report.md", "run_id": run_id}, headers=b)
    assert r.status_code == 404


def test_viewers_cannot_export(env):
    client, _, _ = env
    admin = register(client, "admin@x.io")
    viewer = register(client, "v@x.io")
    org = make_org(client, admin)
    client.post(f"/api/orgs/{org}/members", json={"email": "v@x.io", "role": "viewer"}, headers=admin)
    assert (
        client.post(f"/api/orgs/{org}/exports", json={"kind": "runs.csv"}, headers=viewer).status_code == 403
    )


# --- guidelines + RAG spec check --------------------------------------------------------------


def test_chunk_markdown_keeps_heading_path():
    chunks = chunk_markdown(GUIDE)
    headings = [c.heading for c in chunks]
    assert "Task quality guidelines > Verifiers" in headings
    assert all(len(c.text) <= 1200 for c in chunk_markdown("x " * 5000))


def test_guidelines_and_spec_check(env):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()

    # No guidelines yet: the check says so instead of calling the LLM.
    empty = client.post(f"/api/orgs/{org}/tasks/{task['id']}/spec-checks", headers=h).json()
    assert empty["result"]["issues"] == [] and "No guidelines" in empty["result"]["summary"]

    g = client.post(f"/api/orgs/{org}/guidelines", json={"title": "Quality", "content": GUIDE}, headers=h)
    assert g.status_code == 201 and g.json()["chunk_count"] == 3

    r = client.post(f"/api/orgs/{org}/tasks/{task['id']}/spec-checks", headers=h)
    assert r.status_code == 201
    result = r.json()["result"]
    assert result["issues"][0]["severity"] == "high"
    assert result["issues"][0]["guideline_title"] == "Quality"
    assert result["excerpts"] and result["excerpts"][0]["n"] == 1
    # The prompt carried the task's tests and the retrieved excerpts.
    prompt = client.app.state.llm_factory().prompts[-1]
    assert "test_report.py" in prompt and "Guideline excerpts" in prompt

    history = client.get(f"/api/orgs/{org}/tasks/{task['id']}/spec-checks", headers=h).json()
    assert len(history) == 2

    gid = g.json()["id"]
    assert client.delete(f"/api/orgs/{org}/guidelines/{gid}", headers=h).status_code == 204
    assert client.app.state.guidelines.docs == []


def test_guidelines_are_org_scoped_in_retrieval(env):
    client, _, _ = env
    a = register(client, "a@x.io")
    b = register(client, "b@x.io")
    org_a, org_b = make_org(client, a), make_org(client, b)
    client.post(f"/api/orgs/{org_a}/guidelines", json={"title": "A rules", "content": GUIDE}, headers=a)
    task_b = upload(client, org_b, b, zip_dir(TASK_DIR)).json()
    res = client.post(f"/api/orgs/{org_b}/tasks/{task_b['id']}/spec-checks", headers=b).json()["result"]
    assert res["excerpts"] == []  # org B never sees org A's guidelines


def test_spec_check_without_llm_is_503(env):
    client, _, _ = env
    client.app.state.llm_factory = lambda: None
    h = register(client, "a@x.io")
    org = make_org(client, h)
    task = upload(client, org, h, zip_dir(TASK_DIR)).json()
    assert client.post(f"/api/orgs/{org}/tasks/{task['id']}/spec-checks", headers=h).status_code == 503
