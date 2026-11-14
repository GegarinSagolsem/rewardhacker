"""MCP server tests: the real MCP protocol in-process, against the test API (no network)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")
pytest.importorskip("fastapi")

from api_helpers import TASK_DIR, fake_report, make_org, register  # noqa: E402
from mcp import Client  # noqa: E402

from rewardhacker.api import jobs  # noqa: E402
from rewardhacker.mcp_server import RewardHackerClient, build_server  # noqa: E402


def _key(client, headers, org, role="reviewer") -> str:
    r = client.post(f"/api/orgs/{org}/api-keys", json={"name": "mcp", "role": role}, headers=headers)
    return r.json()["key"]


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


async def _session(server, calls: list[tuple[str, dict]]):
    out = []
    async with Client(server) as c:
        tools = {t.name for t in (await c.list_tools()).tools}
        out.append(tools)
        for name, args in calls:
            out.append(await c.call_tool(name, args))
    return out


def test_key_endpoint(env):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    key = _key(client, h, org)
    info = client.get("/api/auth/key", headers={"Authorization": f"Bearer {key}"}).json()
    assert info == {"org_id": org, "org_name": "Acme RL", "name": "mcp", "role": "reviewer"}
    assert client.get("/api/auth/key", headers=h).status_code == 401  # a user token is not a key


def test_mcp_full_flow(env):
    client, sessions, traces = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    server = build_server(RewardHackerClient("http://testserver", _key(client, h, org), http=client))

    tools, who, invalid, uploaded, listed = asyncio.run(
        _session(
            server,
            [
                ("whoami", {}),
                ("validate_task", {"path": str(TASK_DIR.parent)}),  # no task.yaml there
                ("upload_task", {"path": str(TASK_DIR)}),
                ("list_tasks", {}),
            ],
        )
    )
    assert {"whoami", "upload_task", "start_run", "get_report", "check_guidelines"} <= tools
    assert "Acme RL" in _text(who) and "reviewer" in _text(who)
    assert invalid.is_error and "invalid task" in _text(invalid)
    assert not uploaded.is_error and "weak-output-check" in _text(uploaded)
    assert "`weak-output-check`" in _text(listed) and "not run" in _text(listed)

    # Start by task.yaml id without waiting, let a "worker" finish it, then read results.
    (_, started) = asyncio.run(
        _session(server, [("start_run", {"task": "weak-output-check", "wait": False})])
    )
    assert "queued" in _text(started)
    with sessions() as db:
        jobs.execute(db, jobs.claim_next(db, "w"), traces, probe_fn=lambda s, n: fake_report(s.id))
    run_id = client.get(f"/api/orgs/{org}/runs", headers=h).json()[0]["id"]

    _, summary, report, runs = asyncio.run(
        _session(
            server,
            [
                ("get_run", {"run": run_id[:8]}),
                ("get_report", {"run": run_id}),
                ("list_runs", {"status": "done"}),
            ],
        )
    )
    assert "**EXPLOITABLE**" in _text(summary)
    assert "# RewardHacker report" in _text(report) and "$ echo 'total: 0' > report.txt" in _text(report)
    assert "weak-output-check" in _text(runs)


def test_mcp_guidelines_and_errors(env):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    client.post(
        f"/api/orgs/{org}/guidelines", json={"title": "Q", "content": "# Tests\nCheck values."}, headers=h
    )
    server = build_server(RewardHackerClient("http://testserver", _key(client, h, org), http=client))
    _, up, check, missing = asyncio.run(
        _session(
            server,
            [
                ("upload_task", {"path": str(TASK_DIR)}),
                ("check_guidelines", {"task": "weak-output-check"}),
                ("get_run", {"run": "nonexistent"}),
            ],
        )
    )
    assert not up.is_error
    assert "[HIGH] Tests check format only." in _text(check)
    assert missing.is_error and "no run matches" in _text(missing)


def test_mcp_viewer_key_cannot_start_runs(env):
    client, _, _ = env
    h = register(client, "a@x.io")
    org = make_org(client, h)
    server = build_server(
        RewardHackerClient("http://testserver", _key(client, h, org, role="viewer"), http=client)
    )
    _, up = asyncio.run(_session(server, [("upload_task", {"path": str(TASK_DIR)})]))
    assert up.is_error and "403" in _text(up)
