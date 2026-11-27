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
        params = StdioServerParameters(command=sys.executable, args=["-m", "pharos.server"], cwd=str(ROOT), env={**os.environ, "PHAROS_DB": ":memory:"})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = sorted(t.name for t in (await s.list_tools()).tools)
                dec = await s.call_tool("recovery_brief", {"package_dir": "samples/dev/dev-01-oakridge", "case_id": "mcp1"})
                cmp_ = await s.call_tool("compare_substitution", {"case_id": "mcp1"})
                scr = await s.call_tool("screen_consequences", {"case_id": "mcp1"})
                return names, json.loads(dec.content[0].text), json.loads(cmp_.content[0].text), json.loads(scr.content[0].text)

    names, dec, cmp_, scr = asyncio.run(go())
    assert names == sorted(["assess_delivery_risk", "check_elevator_load", "check_submittal", "compare_substitution", "estimate_arrival", "find_alternatives", "recovery_brief", "screen_consequences"])
    assert dec["answer"] == "no_not_alone" and dec["milestone"]["max_recoverable_weeks"] == 2
    assert any(f["key"] == "electrical:impedance" for f in scr["findings"])
    assert all(c["alternate"]["status"] in {"documented", "not_stated", "could_not_read", "conflicting"} for c in cmp_["fields"])


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("PHAROS_DB", ":memory:")
    from fastapi.testclient import TestClient
    from pharos import core
    from pharos.api import app
    from pharos.store import Store

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
    from pharos.evaluate import list_packages, run_package, summarise

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


def test_milestone_over_mcp_two_unfamiliar_packages_then_a_revised_document():
    """The milestone, through the agent interface: one documented constraint, one genuine unknown, then a revision."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def call(s, name, args):
        return json.loads((await s.call_tool(name, args)).content[0].text)

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "pharos.server"], cwd=str(ROOT), env={**os.environ, "PHAROS_DB": ":memory:"})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                out = {}
                # package 1: a documented constraint (the freight elevator), then a revision that splits the load
                d1 = await call(s, "recovery_brief", {"package_dir": "samples/milestone/m-01-harbor", "case_id": "m1"})
                scr1 = await call(s, "screen_consequences", {"case_id": "m1"})
                d1b = await call(s, "recovery_brief", {"case_id": "m1", "revised_documents": [
                    {"role": "alternate", "path": "samples/milestone/m-01-harbor/alternate_revD.pdf", "revision": "D"}]})
                # package 2: a genuine unknown (a scanned page), then a readable copy
                d2 = await call(s, "recovery_brief", {"package_dir": "samples/milestone/m-02-meridian", "case_id": "m2"})
                d2b = await call(s, "recovery_brief", {"case_id": "m2", "revised_documents": [
                    {"role": "alternate", "path": "samples/milestone/m-02-meridian/alternate_rev3.pdf", "revision": "3"}]})
                out.update(d1=d1, scr1=scr1, d1b=d1b, d2=d2, d2b=d2b)
                return out

    o = asyncio.run(go())
    labels = {f["key"]: f["label"] for f in o["scr1"]["findings"]}
    assert labels["weight:elevator"] == "conclusive" and labels["weight:slab"] == "conclusive"
    assert o["d1"]["answer"] == "no_not_alone" and o["d1"]["milestone"]["max_recoverable_weeks"] == 0
    ch = {c["key"]: (c["from"], c["to"]) for c in o["d1b"]["diff"]["changed"]}
    assert ch["weight:elevator"] == ("conclusive", "cleared") and "electrical:impedance" in o["d1b"]["diff"]["still_open"]
    assert o["d1b"]["diff"]["milestone_moved"] is False and o["d1b"]["version"] == 2
    kinds = {f["key"]: f["label"] for f in o["d2"]["findings"]}
    assert kinds["weight:elevator"] == "could_not_read" and kinds["electrical:impedance"] == "could_not_read"
    assert o["d2"]["readable_copy_requests"] and o["d2"]["answer"] == "only_if"
    assert o["d2b"]["answer"] == "yes" and "electrical:impedance" in o["d2b"]["diff"]["removed"]
