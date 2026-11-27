import json
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from pharos.checks import (
    MassFact, ProductionRange, WeekFact, check_elevator_load, estimate_arrival,
)


FIXTURE = Path(__file__).parent / "fixtures" / "pharos_development_cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


class WeightTests(unittest.TestCase):
    def test_development_cases(self):
        for case in CASES["elevator_cases"]:
            with self.subTest(case=case["id"]):
                facts = {
                    key: MassFact(value=case[key], source=f"{case['id']}:{key}")
                    for key in ("section_kg", "additional_load_kg", "documented_gross_kg", "limit_kg")
                    if case[key] is not None
                }
                result = check_elevator_load(**facts)
                self.assertEqual(result.status, case["expected_weight_status"])
                self.assertEqual(result.sources, {key: fact.source for key, fact in facts.items()})

    def test_conflicting_gross_requires_review(self):
        for gross in (1900, 2200):
            with self.subTest(gross=gross):
                result = check_elevator_load(
                    section_kg=MassFact(value=2000, source="drawing:section"),
                    limit_kg=MassFact(value=3000, source="logistics:capacity"),
                    additional_load_kg=MassFact(value=300, source="rigging:total"),
                    documented_gross_kg=MassFact(value=gross, source="ticket:gross"),
                )
                self.assertEqual(result.status, "needs_review")
                self.assertIsNone(result.gross_kg)

    def test_exactly_at_limit_uses_decimal_arithmetic(self):
        result = check_elevator_load(
            section_kg=MassFact(value="100.125", source="section"),
            additional_load_kg=MassFact(value="0.875", source="rigging"),
            limit_kg=MassFact(value=101, source="limit"),
        )
        self.assertEqual(result.gross_kg, Decimal("101"))
        self.assertEqual(result.status, "within_weight_limit")

    def test_documented_gross_alone_suffices(self):
        result = check_elevator_load(
            section_kg=MassFact(value=3000, source="drawing"),
            documented_gross_kg=MassFact(value=3600, source="gross-ticket"),
            limit_kg=MassFact(value=3500, source="limit"),
        )
        self.assertEqual(result.status, "exceeds_limit")
        self.assertEqual(result.gross_kg, Decimal("3600"))

    def test_reject_invalid_masses(self):
        for value in (-1, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                MassFact(value=value, source="section")
        with self.assertRaises(ValueError):
            check_elevator_load(MassFact(value=500, source="section"), MassFact(value=0, source="limit"))


class ArrivalTests(unittest.TestCase):
    def test_development_cases(self):
        for case in CASES["arrival_cases"]:
            with self.subTest(case=case["id"]):
                low, high = case["quoted_production_weeks"]
                approval_week = case["approval_week"]
                result = estimate_arrival(
                    quoted_production_weeks=ProductionRange(minimum=low, maximum=high, source="quote:2"),
                    transit_weeks=WeekFact(value=case["transit_weeks"], source="freight:8"),
                    approval_week=None if approval_week is None else WeekFact(value=approval_week, source="schedule:3"),
                )
                if approval_week is None:
                    self.assertEqual(result.status, "needs_approval_date")
                    self.assertIsNone(result.onsite_week_range)
                    self.assertEqual(list(result.weeks_after_approval), case["expected_weeks_after_approval"])
                    self.assertNotIn("approval_week", result.sources)
                else:
                    self.assertEqual(result.status, "conditional_on_quoted_terms")
                    self.assertEqual(list(result.onsite_week_range), case["expected_onsite_week_range"])
                    self.assertEqual(result.sources["approval_week"], "schedule:3")

    def test_week_zero_and_zero_transit(self):
        result = estimate_arrival(
            ProductionRange(minimum=3, maximum=3, source="quote"),
            WeekFact(value=0, source="onsite delivery term"), WeekFact(value=0, source="release"),
        )
        self.assertEqual(result.onsite_week_range, (3, 3))

    def test_invalid_evidence_and_ranges(self):
        for value in (-1, 2.5, True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                WeekFact(value=value, source="schedule")
        with self.assertRaises(ValidationError):
            ProductionRange(minimum=9, maximum=4, source="quote")
        with self.assertRaises(ValidationError):
            MassFact(value=10, source="  ")
