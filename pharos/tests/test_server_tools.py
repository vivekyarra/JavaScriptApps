"""Fresh-client MCP checks for the five specialists, with outbound sockets disabled in the server process."""
import json
import os
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
NO_NET = (
    "import socket\n"
    "def _blocked(*a, **k):\n    raise OSError('network disabled for offline test')\n"
    "socket.socket.connect = _blocked\nsocket.create_connection = _blocked\n"
    "from pharos.server import main\nmain()\n"
)
SPEC = "Manufacturer: Orig (synthetic)\nModel: O-1\nRated capacity: 2,500 kVA\nVector group: Dyn11\nTotal losses: maximum 14.0 kW\n"
SUB = "Manufacturer: Alt (synthetic)\nModel: A-1\nRated capacity: 2,500 kVA\nVector group: Dyn11\nTotal losses: 15.5 kW\n"
CSV = "manufacturer,model,rated_kva,winding_config,heat_loss_kw\nAlpha Fictional,AF-1,2500,Dyn11,12.5\nBeta Fictional,BF-1,2000,Dyn11,11\n"


class ServerTools(unittest.IsolatedAsyncioTestCase):
    async def test_specialists_work_offline_through_a_fresh_client(self):
        params = StdioServerParameters(command=sys.executable, args=["-c", NO_NET], cwd=ROOT, env={**os.environ, "PHAROS_DB": ":memory:"})
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            self.assertTrue({"check_submittal", "find_alternatives", "screen_consequences", "assess_delivery_risk", "estimate_arrival", "recovery_brief"} <= names)
            res = await s.call_tool("check_submittal", {"documents": [
                {"role": "spec", "text": SPEC, "name": "spec.txt"}, {"role": "alternate", "text": SUB, "name": "sub.txt"}]})
            self.assertFalse(res.isError, res.content)
            out = json.loads(res.content[0].text)
            verdict = {q["field"]: q["verdict"] for q in out["requirements"]}
            self.assertEqual(verdict["heat_loss_kw"], "deviates")
            self.assertEqual(verdict["rated_kva"], "complies")
            alt = await s.call_tool("find_alternatives", {"documents": [
                {"role": "spec", "text": SPEC, "name": "spec.txt"}, {"role": "library", "text": CSV, "name": "lib.csv"}]})
            self.assertFalse(alt.isError, alt.content)
            a = json.loads(alt.content[0].text)
            self.assertEqual(a["candidates"][0]["model"], "AF-1")
            self.assertEqual(a["candidates"][0]["verdict"], "supported")
            self.assertEqual([c["verdict"] for c in a["candidates"]][-1], "falls_short")

    async def test_find_alternatives_without_spec_is_a_tool_error(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "pharos.server"], cwd=ROOT, env={**os.environ, "PHAROS_DB": ":memory:"})
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("find_alternatives", {"documents": [{"role": "library", "text": CSV, "name": "lib.csv"}]})
            self.assertTrue(res.isError)


def test_api_new_endpoints_and_library_guard():
    from fastapi.testclient import TestClient

    from pharos.api import app

    c = TestClient(app)
    docs = [{"role": "spec", "text": SPEC, "name": "spec.txt"}, {"role": "alternate", "text": SUB, "name": "sub.txt"}]
    r = c.post("/api/tools/check-submittal", json={"documents": docs})
    assert r.status_code == 200 and r.json()["counts"]["deviates"] == 1
    r = c.post("/api/tools/find-alternatives", json={"documents": [docs[0], {"role": "library", "text": CSV, "name": "lib.csv"}]})
    assert r.status_code == 200 and r.json()["candidates"][0]["model"] == "AF-1"
    assert c.post("/api/tools/find-alternatives", json={"documents": [docs[0]], "library_dir": "/etc"}).status_code == 400
