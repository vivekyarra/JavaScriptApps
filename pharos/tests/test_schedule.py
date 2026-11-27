import json
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from pharos.checks import WeekFact
from pharos.schedule import PurchaseOrderLine, assess_delivery_risk


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/pharos_development_cases.json").read_text(encoding="utf-8"))


def ready(week, source):
    return {"week": week, "source": source}


def weeks(value, source):
    return {"value": value, "source": source}


class ScheduleFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_fixtures_over_stdio(self):
        server = StdioServerParameters(command=sys.executable, args=["-m", "pharos.server"], cwd=ROOT)
        async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as client:
            await client.initialize()
            metadata = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertIsNotNone(metadata["assess_delivery_risk"].outputSchema)

            for case in FIXTURES["milestone_cases"]:
                with self.subTest(case=case["id"]):
                    i, e = case["input"], case["expected"]
                    response = await client.call_tool("assess_delivery_risk", {
                        "po_lines": [
                            {"line_id": "transformer", "baseline": ready(i["original_transformer_ready_week"], "PO-1 row 1"),
                             "proposed": ready(i["alternate_transformer_ready_week"], "alternate quote p2")},
                            {"line_id": "switchgear", "baseline": ready(i["switchgear_ready_week"], "PO-2 row 3")},
                        ],
                        "post_handoff_weeks": weeks(i["installation_and_testing_weeks"], "schedule activity 9"),
                        "recovery_target_weeks": weeks(i["target_recovery_weeks"], "buyer brief p1"),
                    })
                    self.assertFalse(response.isError, response.content)
                    result = response.structuredContent
                    self.assertEqual(result["baseline"]["milestone_week"], e["baseline_milestone_week"])
                    self.assertEqual(result["proposed"]["milestone_week"], e["earliest_alternate_milestone_week"])
                    self.assertEqual(result["proposed"]["controlling_line_ids"], e["alternate_controlling_items"])
                    self.assertEqual(result["potential_recovery_weeks"], e["potential_recovery_weeks"])
                    self.assertEqual(result["latest_handoff_week_for_recovery"], e["latest_switchgear_ready_week_for_target"])
                    verdict = "met_on_stated_dates" if e["target_possible_with_swap_alone"] else "not_met"
                    self.assertEqual(result["recovery_target_status"], verdict)
                    first = result["proposed"]["lines_by_urgency"][0]
                    self.assertEqual(first["ready"]["source"], "PO-2 row 3")
                    self.assertEqual(first["action"], "confirm_date" if verdict == "met_on_stated_dates" else "seek_earlier_date")

            case = FIXTURES["po_slack_case"]
            i, e = case["input"], case["expected"]
            response = await client.call_tool("assess_delivery_risk", {
                "po_lines": [
                    {"line_id": "transformer", "baseline": ready(i["transformer_ready_week"], "PO-1 row 1")},
                    {"line_id": "switchgear", "baseline": ready(i["switchgear_previous_ready_week"], "PO-2 row 3"),
                     "proposed": ready(i["switchgear_revised_ready_week"], "vendor update p1")},
                ],
                "required_handoff_week": weeks(i["required_joint_handoff_week"], "schedule row 8"),
                "post_handoff_weeks": weeks(i["installation_and_testing_weeks"], "schedule row 9"),
            })
            self.assertFalse(response.isError, response.content)
            result = response.structuredContent
            self.assertEqual(result["baseline"]["milestone_week"], e["milestone_week_before_update"])
            self.assertEqual(result["proposed"]["milestone_week"], e["milestone_week_after_update"])
            first, second = result["proposed"]["lines_by_urgency"]
            self.assertEqual(first["line_id"], e["risk_rank_first"])
            self.assertEqual(second["change_from_baseline_weeks"], e["switchgear_slip_weeks"])
            self.assertEqual(second["float_to_handoff_weeks"], e["switchgear_remaining_slack_weeks"])
            self.assertEqual(second["margin_to_deadline_weeks"], e["switchgear_remaining_slack_weeks"])
            self.assertEqual(second["action"], e["switchgear_schedule_action"])


class ScheduleBoundaryTests(unittest.TestCase):
    tail = WeekFact(value=0, source="handoff is the milestone")

    def test_tied_controlling_items_and_unchanged_lines(self):
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="B", baseline=ready(0, "B-0"), proposed=ready(3, "B-1")),
            PurchaseOrderLine(line_id="A", baseline=ready(3, "A-0")),
            PurchaseOrderLine(line_id="C", baseline=ready(3, "C-0")),
        ], self.tail)
        self.assertEqual(result.baseline.controlling_line_ids, ["A", "C"])
        self.assertEqual(result.proposed.controlling_line_ids, ["A", "B", "C"])
        self.assertEqual([r.line_id for r in result.proposed.lines_by_urgency], ["A", "B", "C"])
        self.assertEqual(result.potential_recovery_weeks, 0)
        self.assertIsNone(result.recovery_target_status)

    def test_withdrawn_ready_date_does_not_reuse_baseline(self):
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="gear", baseline=ready(22, "quote"), proposed=ready(None, "vendor: TBD")),
            PurchaseOrderLine(line_id="UPS", baseline=ready(20, "PO-7")),
        ], self.tail, recovery_target_weeks=WeekFact(value=1, source="buyer"))
        self.assertEqual(result.proposed.status, "needs_dates")
        self.assertIsNone(result.proposed.milestone_week)
        self.assertEqual(result.proposed.controlling_line_ids, [])
        self.assertIsNone(result.potential_recovery_weeks)
        self.assertEqual(result.recovery_target_status, "needs_data")
        undated = result.proposed.lines_by_urgency[0]
        self.assertEqual(undated.action, "request_ready_date")
        self.assertEqual(undated.ready.source, "vendor: TBD")

    def test_condition_prevents_unconditional_recovery(self):
        conditional = ready(10, "expedite quote")
        conditional["open_conditions"] = [{"description": "Route approval pending", "source": "logistics p4"}]
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="pump", baseline=ready(30, "PO p2"), proposed=conditional),
            PurchaseOrderLine(line_id="starter", baseline=ready(22, "PO p3")),
        ], self.tail, recovery_target_weeks=WeekFact(value=7, source="target"))
        self.assertEqual(result.potential_recovery_weeks, 8)
        self.assertEqual(result.recovery_target_status, "conditional_on_open_items")
        pump = result.proposed.lines_by_urgency[1]
        self.assertEqual(pump.action, "resolve_condition")
        self.assertEqual(pump.ready.open_conditions[0].source, "logistics p4")

    def test_unknown_baseline_allows_proposed_date_but_no_recovery_claim(self):
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="X", baseline=ready(None, "old PO: TBD"), proposed=ready(8, "new quote")),
        ], self.tail, recovery_target_weeks=WeekFact(value=3, source="buyer"))
        self.assertIsNone(result.baseline.milestone_week)
        self.assertEqual(result.proposed.milestone_week, 8)
        self.assertIsNone(result.potential_recovery_weeks)
        self.assertIsNone(result.latest_handoff_week_for_recovery)
        self.assertEqual(result.recovery_target_status, "needs_data")

    def test_conditional_baseline_does_not_become_a_firm_target(self):
        original = ready(32, "original planning estimate")
        original["open_conditions"] = [{"description": "Awaiting release", "source": "approvals row 3"}]
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="X", baseline=original, proposed=ready(19, "new confirmation")),
        ], self.tail, recovery_target_weeks=WeekFact(value=4, source="buyer"))
        self.assertEqual(result.potential_recovery_weeks, 13)
        self.assertEqual(result.baseline.status, "conditional_on_open_items")
        self.assertEqual(result.recovery_target_status, "needs_data")

    def test_keep_order_is_schedule_only_and_need_by_can_be_stricter(self):
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="X", baseline=ready(24, "PO 1")),
            PurchaseOrderLine(line_id="Y", baseline=ready(20, "PO 2")),
        ], self.tail, required_handoff_week=WeekFact(value=19, source="need by"),
            recovery_target_weeks=WeekFact(value=2, source="recovery request"))
        self.assertIsNone(result.proposed)
        self.assertIsNone(result.potential_recovery_weeks)
        self.assertEqual(result.latest_handoff_week_for_recovery, 22)
        self.assertEqual(result.action_deadline_week, 19)
        second = result.baseline.lines_by_urgency[1]
        self.assertEqual((second.float_to_handoff_weeks, second.margin_to_deadline_weeks), (4, -1))
        self.assertEqual(second.action, "seek_earlier_date")

    def test_negative_recovery_is_not_clamped(self):
        result = assess_delivery_risk([
            PurchaseOrderLine(line_id="X", baseline=ready(0, "PO"), proposed=ready(5, "revision")),
        ], self.tail, recovery_target_weeks=WeekFact(value=0, source="no slip"))
        self.assertEqual(result.potential_recovery_weeks, -5)
        self.assertEqual(result.recovery_target_status, "not_met")
        self.assertEqual(result.latest_handoff_week_for_recovery, 0)

    def test_invalid_inputs(self):
        line = PurchaseOrderLine(line_id=" PO-10 ", baseline=ready(4, "record"))
        with self.assertRaisesRegex(ValueError, "unique"):
            assess_delivery_risk([line, PurchaseOrderLine(line_id="PO-10", baseline=ready(2, "record"))], self.tail)
        with self.assertRaisesRegex(ValueError, "at least one"):
            assess_delivery_risk([], self.tail)
        for bad in (-2, True, 1.25):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                PurchaseOrderLine(line_id="PO", baseline=ready(bad, "vendor"))
