import unittest

from pharos.checks import ComparableObservation, ProductionRange, WeekFact, estimate_arrival


def wf(v, s="schedule row"):
    return WeekFact(value=v, source=s)


def obs(q, a, n):
    return ComparableObservation(quoted_weeks=q, actual_weeks=a, source=f"delivery log row {n}")


class ArrivalExtensions(unittest.TestCase):
    q = ProductionRange(minimum=22, maximum=24, source="quote rev C p2")

    def test_default_behaviour_is_unchanged(self):
        r = estimate_arrival(self.q, wf(2), wf(6))
        self.assertEqual(r.status, "conditional_on_quoted_terms")
        self.assertEqual(r.onsite_week_range, (30, 32))
        self.assertEqual(r.weeks_after_approval, (24, 26))
        self.assertEqual(r.start, "approval")
        self.assertIsNone(r.reference)

    def test_order_start_uses_the_order_week_not_an_approval_date(self):
        r = estimate_arrival(self.q, wf(2), start="order", order_week=wf(0, "PO release"))
        self.assertEqual(r.status, "conditional_on_quoted_terms")
        self.assertEqual(r.onsite_week_range, (24, 26))
        self.assertIsNone(r.weeks_after_approval)
        self.assertEqual(r.weeks_after_start, (24, 26))

    def test_order_start_without_an_order_week_asks_for_it(self):
        r = estimate_arrival(self.q, wf(2), start="order")
        self.assertEqual(r.status, "needs_order_date")
        self.assertIsNone(r.onsite_week_range)

    def test_fewer_than_five_comparables_are_not_used(self):
        r = estimate_arrival(self.q, wf(2), wf(6), comparable_observations=[obs(20, 26, 1), obs(24, 25, 2)])
        self.assertIsNone(r.reference)
        self.assertIn("at least 5", r.reference_note)

    def test_five_or_more_comparables_give_an_observed_spread_not_a_percentile(self):
        o = [obs(20, 20, 1), obs(20, 22, 2), obs(24, 26, 3), obs(24, 30, 4), obs(22, 22, 5)]
        r = estimate_arrival(self.q, wf(2), wf(6), comparable_observations=o)
        self.assertEqual(r.reference.observations, 5)
        self.assertEqual((r.reference.slip_ratio_min, r.reference.slip_ratio_max), (1.0, 1.25))
        self.assertIn("not a statistical forecast", r.reference.basis)
        self.assertEqual(r.onsite_week_range, (30, 32))               # the quote bounds are unchanged
        self.assertEqual(r.reference_onsite_week_range, (6 + 24, 6 + 32))  # 22*1.0+2 .. ceil(24*1.25)+2
        self.assertNotIn("percentile", r.reference.basis.replace("not a", ""))


if __name__ == "__main__":
    unittest.main()
