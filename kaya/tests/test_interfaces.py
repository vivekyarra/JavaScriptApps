"""MCP, API and sample-package regression tests: all interfaces share one core."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_mcp_exposes_exactly_three_tools_and_returns_structured_output():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "knockon.mcp_server"], cwd=str(ROOT), env={**os.environ, "KNOCKON_DB": ":memory:"})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = sorted(t.name for t in (await s.list_tools()).tools)
                dec = await s.call_tool("decide_and_ask", {"package_dir": "samples/dev/dev-01-oakridge", "case_id": "mcp1"})
                cmp_ = await s.call_tool("compare_substitution", {"case_id": "mcp1"})
                scr = await s.call_tool("screen_consequences", {"case_id": "mcp1"})
                return names, json.loads(dec.content[0].text), json.loads(cmp_.content[0].text), json.loads(scr.content[0].text)

    names, dec, cmp_, scr = asyncio.run(go())
    assert names == ["compare_substitution", "decide_and_ask", "screen_consequences"]
    assert dec["answer"] == "no_not_alone" and dec["milestone"]["max_recoverable_weeks"] == 2
    assert any(f["key"] == "electrical:impedance" for f in scr["findings"])
    assert all(c["alternate"]["status"] in {"documented", "not_stated", "could_not_read", "conflicting"} for c in cmp_["fields"])


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("KNOCKON_DB", ":memory:")
    from fastapi.testclient import TestClient
    from knockon import core
    from knockon.api import app
    from knockon.store import Store

    core.set_default_store(Store(":memory:"))
    return TestClient(app)


def test_api_matches_mcp_core_and_guards_paths(client):
    r = client.post("/api/cases/from-sample", data={"sample_id": "dev/dev-01-oakridge", "case_id": "api1"})
    assert r.status_code == 200 and r.json()["answer"] == "no_not_alone"
    r2 = client.post("/api/cases/api1/apply-sample-revision", data={"sample_id": "dev/dev-01-oakridge", "label": "B"})
    assert r2.status_code == 200 and r2.json()["diff"]["changed"][0]["to"] == "cleared"
    assert client.get("/api/cases/api1").json()["history"][-1]["version"] == 2
    assert client.post("/api/tools/decide", json={"documents": [{"role": "alternate", "path": "/etc/passwd"}]}).status_code == 400
    assert client.post("/api/tools/decide", json={"package_dir": "/etc"}).status_code == 400
    page = client.get("/api/cases/api1/compare").json()
    sha = page["documents"][0]["sha256"]
    assert client.get(f"/api/cases/api1/page?sha={sha}&page=1").status_code == 200


def test_api_upload_flow(client):
    d = ROOT / "samples/dev/dev-02-birch"
    files = [("files", (n, (d / n).read_bytes())) for n in ["spec.pdf", "original.pdf", "alternate.pdf", "logistics.pdf", "schedule.json"]]
    r = client.post("/api/upload", files=files, data={"roles": "spec,original,alternate,logistics,schedule", "recovery_target_weeks": "12"})
    assert r.status_code == 200 and r.json()["answer"] == "yes"
    bad = client.post("/api/upload", files=files, data={"roles": "spec,original"})
    assert bad.status_code == 400


def test_dev_and_milestone_sets_pass_in_full():
    from knockon.evaluate import list_packages, run_package, summarise

    for name in ("dev", "milestone"):
        results = [run_package(p) for p in list_packages(name)]
        assert results, name
        s = summarise(results)
        n, d = s["fields_correct"].split("/")
        assert n == d, (name, s)
        n, d = s["findings_correct"].split("/")
        assert n == d and s["false_positive_findings"] == 0 and s["electrical_clearances_issued"] == 0, (name, s)
        n, d = s["decision_checks_passed"].split("/")
        assert n == d, (name, s)
        n, d = s["revision_checks_passed"].split("/")
        assert n == d, (name, s)
