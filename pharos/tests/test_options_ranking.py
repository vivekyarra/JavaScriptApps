"""Recovery options compared at the same milestone, the PO-line ranking, and 'keep the order'."""
import copy

from helpers import BASE_ALT, SCHEDULE, run

ORIG = BASE_ALT.replace("TV-1", "OLD-1").replace("Lead time: 30 weeks ARO", "Lead time: 82 weeks ARO")
SPEC = "Rated power (ONAN): not less than 2,500 kVA\nImpedance 5.00 % (tolerance +/-7.5 %)\n"
LOG = "Freight elevator capacity: 3,600 kg\nRigging and handling equipment weight per lift: 300 kg\nGeneral notes: synthetic.\n"
EXPEDITE = {"id": "expedite-sg", "type": "expedite", "line": "SG", "new_week": 76, "description": "Expedite the switchgear",
            "premium": {"amount": 42000, "currency": "USD", "source": "Quote Q-9 p2"},
            "conditions": [{"description": "Factory slot confirmed", "source": "Quote Q-9 p2"}]}


def sched(**over):
    s = copy.deepcopy(SCHEDULE)
    s.update(over)
    return s


def go(**kw):
    kw.setdefault("original", ORIG)
    kw.setdefault("spec", SPEC)
    kw.setdefault("logistics", LOG)
    kw.setdefault("target", 4)
    res, _ = run(**kw)
    return res


def opt(res, oid):
    return next(o for o in res.options if o["id"] == oid)


def test_the_substitution_is_always_an_option_and_reports_its_recovery():
    res = go()
    s = opt(res, "substitute")
    assert s["recovery_weeks_best"] == 2 and s["meets_target"] is False
    assert s["incremental_cost"] is None and "request a quote" in s["cost_note"]
    assert "No option on the table reaches the target" in res.recommendation


def test_a_priced_expedite_alone_does_not_help_when_the_transformer_controls():
    res = go(schedule=sched(options=[EXPEDITE]))
    e = opt(res, "expedite-sg")
    assert e["recovery_weeks_best"] == 0 and e["meets_target"] is False
    assert e["incremental_cost"] == {"amount": 42000.0, "currency": "USD", "sources": ["Quote Q-9 p2"]}


def test_substitute_plus_expedite_reaches_the_target_and_is_recommended_with_its_documented_cost():
    res = go(schedule=sched(options=[EXPEDITE]))
    c = opt(res, "substitute+expedite")
    assert c["recovery_weeks_best"] == 6 and c["meets_target"] is True       # handoff 82 -> max(30, 76) = 76
    assert "Factory slot confirmed" in c["conditions"]
    assert c["incremental_cost"]["amount"] == 42000.0
    assert res.recommendation.startswith("Recommended: Take the alternate")
    assert "42,000 USD" in res.recommendation and "Quote Q-9 p2" in res.recommendation


def test_cost_is_only_what_a_quote_supports():
    unpriced = {k: v for k, v in EXPEDITE.items() if k != "premium"}
    res = go(schedule=sched(options=[unpriced]))
    e = opt(res, "expedite-sg")
    assert e["incremental_cost"] is None and "No price is assumed" in e["cost_note"]


def test_a_sourced_substitution_price_difference_is_reported():
    res = go(schedule=sched(substitution_cost={"amount": 15000, "currency": "USD", "source": "Alternate quote p3"}))
    assert opt(res, "substitute")["incremental_cost"]["amount"] == 15000.0


def test_late_but_with_slack_is_keep_the_order():
    s = sched(items=[{"id": "T1", "name": "Transformer T1", "baseline_arrival_week": 75},
                     {"id": "SG", "name": "Switchgear", "arrival_week": 82, "vendor": "Switchgear vendor"}])
    res = go(schedule=s, target=None)
    rows = {r["line_id"]: r for r in res.ranking}
    assert rows["T1"]["action"] == "keep_order" and rows["T1"]["float_to_handoff_weeks"] == 7
    assert res.ranking[0]["line_id"] == "SG"   # the controlling line is ranked first
    assert rows["SG"]["float_to_handoff_weeks"] == 0


def test_the_ranking_marks_what_must_be_earlier_to_reach_a_target():
    res = go(target=4)
    rows = {r["line_id"]: r for r in res.ranking}
    assert rows["SG"]["action"] == "seek_earlier_date" and rows["SG"]["margin_to_deadline_weeks"] == -2   # due 80, needed by 78: negative margin means earlier
    assert rows["T1"]["action"] == "seek_earlier_date" and rows["T1"]["margin_to_deadline_weeks"] == -4


def test_the_arrival_window_is_part_of_the_brief():
    res = go()
    assert res.arrival["status"] == "conditional_on_quoted_terms" and res.arrival["start"] == "order"
    assert res.arrival["onsite_week_range"] == [30, 30]


def test_fractional_lead_times_round_up():
    res = go(alt=BASE_ALT.replace("30 weeks ARO", "7 months ARO"))
    assert res.arrival["onsite_week_range"] == [31, 31]          # 7 months = 30.33 weeks, rounded up
    assert res.milestone.weeks_earlier_alternate_ships == 51
