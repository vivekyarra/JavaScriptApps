import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_discover_call_and_recover_from_invalid_input(self):
        server = StdioServerParameters(
            command=sys.executable, args=["-m", "pharos.server"], cwd=Path(__file__).resolve().parents[1],
        )
        async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as client:
            await client.initialize()
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            for name in ("estimate_arrival", "check_elevator_load"):
                self.assertIsNotNone(tools[name].outputSchema)

            invalid = await client.call_tool("estimate_arrival", {
                "quoted_production_weeks": {"minimum": 9, "maximum": 3, "source": "quote rev B p2"},
                "transit_weeks": {"value": 2, "source": "freight p3"},
            })
            self.assertTrue(invalid.isError)
            arrival = await client.call_tool("estimate_arrival", {
                "quoted_production_weeks": {"minimum": 7, "maximum": 10, "source": "quote rev B p2"},
                "transit_weeks": {"value": 1, "source": "freight p3"},
                "approval_week": {"value": 5, "source": "schedule row 23"},
            })
            self.assertFalse(arrival.isError, arrival.content)
            self.assertEqual(arrival.structuredContent["onsite_week_range"], [13, 16])
            self.assertEqual(arrival.structuredContent["sources"]["transit_weeks"], "freight p3")

            weight = await client.call_tool("check_elevator_load", {
                "section_kg": {"value": 2300, "source": "submittal p4"},
                "limit_kg": {"value": 3000, "source": "logistics row 6"},
            })
            self.assertFalse(weight.isError, weight.content)
            self.assertEqual(weight.structuredContent["status"], "needs_data")
            self.assertIsNone(weight.structuredContent["gross_kg"])
