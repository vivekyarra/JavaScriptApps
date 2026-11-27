import copy

import pytest

from helpers import BASE_ALT, SCHEDULE, run
from pharos import core
from pharos.schemas import CaseInput, DocumentInput
from pharos.store import Store

LOG = """Freight elevator capacity: 3,600 kg
Rigging and handling equipment weight per lift: 300 kg
Delivery door clear opening (W x H): 2,400 x 2,600 mm
Floor loading limit: 3,000 kg/m2
Cooling capacity available for this unit: 20 kW
Overhead clearance (ceiling): 3,000 mm
"""
SPEC = """Rated power (ONAN): not less than 2,500 kVA
Primary voltage 13.8 kV, delta
Secondary voltage 480Y/277 V
Impedance 5.75 % (tolerance +/-7.5 %)
Winding connection Dyn11
"""
ORIG_SAME = BASE_ALT.replace("Impedance (%Z) at 75 C: 5.00 %", "Impedance (%Z) at 75 C: 5.00 %").replace("TV-1", "OLD-1").replace("Lead time: 30 weeks ARO", "Lead time: 82 weeks ARO")


def labels(res):
    return {f.key: f.label for f in res.findings}


def with_sched(**over):
    s = copy.deepcopy(SCHEDULE)
    s.update(over)
    return s


def switchgear(week):
    s = copy.deepcopy(SCHEDULE)
    s["items"][1]["arrival_week"] = week
    return s


# ------------------------------------------------------------------ physical screening
def test_elevator_conclusive_then_cleared():
    res, _ = run(logistics="Freight elevator capacity: 2,000 kg\nGeneral notes: synthetic delivery plan for testing only.")
    f = next(f for f in res.findings if f.key == "weight:elevator")
    assert f.label == "conclusive" and f.requirement_evidence and f.supplier_evidence
    res, _ = run(logistics=LOG)
    assert labels(res)["weight:elevator"] == "cleared"


def test_total_weight_bounds_every_section():
    alt = BASE_ALT.replace("Heaviest shipping section: 3,000 kg\n", "").replace("Total weight: 7,000 kg", "Total weight: 3,200 kg")
    res, _ = run(alt=alt, logistics=LOG)
    f = next(f for f in res.findings if f.key == "weight:elevator")
    assert f.label == "cleared" and "bounded" in (f.scope_note or "").lower()


def test_total_over_limit_without_split_is_not_stated_not_conclusive():
    alt = BASE_ALT.replace("Heaviest shipping section: 3,000 kg\n", "").replace("Total weight: 7,000 kg", "Total weight: 9,000 kg")
    res, _ = run(alt=alt, logistics=LOG)
    f = next(f for f in res.findings if f.key == "weight:elevator")
    assert f.label == "not_stated" and f.follow_up.kind == "vendor"


def test_door_slab_ceiling_heat():
    res, _ = run(logistics=LOG)
    lab = labels(res)
    assert lab["dims:door"] == "cleared" and lab["dims:ceiling"] == "cleared" and lab["heat:cooling"] == "cleared"
    assert lab["weight:slab"] == "cleared"
    res, _ = run(logistics="Delivery door clear opening (W x H): 1,200 x 2,600 mm\nFloor loading limit: 1,000 kg/m2\nCooling capacity available for this unit: 5 kW\nOverhead clearance (ceiling): 2,000 mm\nGeneral notes: synthetic.")
    lab = labels(res)
    assert lab["dims:door"] == "conclusive" and lab["weight:slab"] == "conclusive"
    assert lab["heat:cooling"] == "conclusive" and lab["dims:ceiling"] == "conclusive"


def test_cleared_findings_state_their_scope():
    res, _ = run(logistics=LOG)
    cleared = [f for f in res.findings if f.label == "cleared"]
    assert cleared and all(f.scope_note for f in cleared)


def test_project_facts_supply_constraints_with_evidence():
    res, _ = run(facts={"elevator_capacity_kg": 2000})
    f = next(f for f in res.findings if f.key == "weight:elevator")
    assert f.label == "conclusive" and f.requirement_evidence[0].document == "project_facts"


def test_missing_constraints_are_listed_not_invented():
    res, _ = run()
    assert not [f for f in res.findings if f.topic == "physical"]
    assert any("elevator" in m for m in res.missing_project_facts)


# ------------------------------------------------------------------ electrical: never a clearance
@pytest.mark.parametrize("alt_z", ["5.00", "7.00"])
def test_impedance_change_is_engineer_review_in_both_directions(alt_z):
    alt = BASE_ALT.replace("5.00 %", f"{alt_z} %")
    orig = ORIG_SAME.replace("5.00 %", "5.75 %")
    res, _ = run(alt=alt, original=orig, spec=SPEC)
    f = next(f for f in res.findings if f.key == "electrical:impedance")
    assert f.label == "needs_engineer" and f.follow_up.kind == "engineer" and f.follow_up.question
    assert not [x for x in res.findings if x.topic == "electrical" and x.label in {"cleared", "conclusive"}]


def test_impedance_unchanged_has_no_finding_and_missing_is_not_stated():
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"))
    assert "electrical:impedance" not in labels(res)
    res, _ = run(alt=BASE_ALT.replace("Impedance (%Z) at 75 C: 5.00 %\n", ""), original=ORIG_SAME)
    f = next(f for f in res.findings if f.key == "electrical:impedance")
    assert f.label == "not_stated" and "impedance" in f.follow_up.question.lower()


def test_spec_deviations():
    res, _ = run(alt=BASE_ALT.replace("2,500 kVA", "2,000 kVA"), spec=SPEC, original=ORIG_SAME)
    assert labels(res)["spec:kva"] == "conclusive"
    res, _ = run(alt=BASE_ALT.replace("480Y/277 V", "208Y/120 V"), spec=SPEC, original=ORIG_SAME)
    assert labels(res)["spec:secondary_voltage"] == "conclusive"
    res, _ = run(alt=BASE_ALT.replace("Dyn11", "Yyn0"), spec=SPEC, original=ORIG_SAME.replace("Dyn11", "Dyn11"))
    assert labels(res)["spec:winding"] == "needs_engineer"


# ------------------------------------------------------------------ decide_and_ask
def test_no_target_still_reports_maximum_recoverable():
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"))
    assert res.answer == "no_target" and res.milestone.max_recoverable_weeks == 2
    assert res.milestone.weeks_earlier_alternate_ships == 52


def test_no_not_alone_names_what_else_must_move():
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), target=4)
    assert res.answer == "no_not_alone"
    r = res.requirements_to_hit_target[0]
    assert r.item == "Switchgear" and r.must_be_ready_by_week == 78 and r.currently_week == 80
    assert res.next_call["party"] == "Switchgear vendor"
    assert "2 weeks" in res.headline and "week 78" in res.headline


def test_yes_when_everything_is_settled():
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), logistics=LOG, schedule=switchgear(60), target=12)
    assert res.answer == "yes", res.headline
    assert res.milestone.max_recoverable_weeks == 22 and not res.open


def test_open_items_turn_yes_into_only_if():
    res, _ = run(original=ORIG_SAME.replace("5.00 %", "5.75 %"), spec=SPEC, logistics=LOG, schedule=switchgear(60), target=12)
    assert res.answer == "only_if" and any("open items" in c for c in res.conditions)


def test_unresolved_blocker_is_potential_recovery_not_promise():
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), logistics="Freight elevator capacity: 2,000 kg\nGeneral notes: synthetic.", schedule=switchgear(60), target=12)
    assert res.answer == "only_if"
    assert "potential recovery, not a promised saving" in res.headline
    assert "unknown" in res.cost_note.lower()


def test_dated_alternative_route_is_counted():
    sched = switchgear(60)
    sched["alternate_routes"] = [{"description": "crane lift via dock", "ready_week": 40}]
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), logistics="Freight elevator capacity: 2,000 kg\nGeneral notes: synthetic.", schedule=sched, target=12)
    assert res.answer == "yes" and any("week 40" in c for c in res.conditions)


def test_alternate_itself_too_late_is_no():
    res, _ = run(alt=BASE_ALT.replace("30 weeks ARO", "90 weeks ARO"), original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), target=4)
    assert res.answer == "no" and "week 90" in res.headline


def test_needs_data_without_schedule_or_lead_time():
    res, _ = run(schedule=None, target=4)
    assert res.answer == "needs_data" and any("schedule" in m for m in res.missing_project_facts)
    res, _ = run(alt=BASE_ALT.replace("Lead time: 30 weeks ARO\n", ""), target=4)
    assert res.answer == "needs_data" and any("lead time" in q.lower() for q in res.vendor_questions)


def test_start_condition_not_stated_gives_a_range():
    alt = BASE_ALT.replace("30 weeks ARO", "26 weeks")
    res, _ = run(alt=alt, original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), schedule=switchgear(10), target=4)
    m = res.milestone
    assert m.max_recoverable_weeks == 56 and m.conservative_recoverable_weeks == 52
    assert any("start condition is not stated" in c for c in res.conditions)
    assert any("order placement or from approved drawings" in q for q in res.vendor_questions)


def test_lead_time_from_approval_adds_approval_duration():
    alt = BASE_ALT.replace("30 weeks ARO", "36 weeks after approved drawings")
    res, _ = run(alt=alt, original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), schedule=switchgear(10), target=4)
    assert res.milestone.weeks_earlier_alternate_ships == 82 - 40


def test_lead_time_range_uses_both_ends():
    alt = BASE_ALT.replace("30 weeks ARO", "28-30 weeks ARO")
    res, _ = run(alt=alt, original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), schedule=switchgear(10), target=4)
    assert res.milestone.max_recoverable_weeks - res.milestone.conservative_recoverable_weeks == 2


def test_costs_only_from_a_cited_source():
    sched = switchgear(60)
    sched["remediation"] = [{"description": "spreader frame", "weeks": 1, "cost": {"amount": 12000, "currency": "USD", "source": "Quote Q-7"}},
                            {"description": "unquoted work", "weeks": 1}]
    res, _ = run(original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), schedule=sched, target=4)
    assert [c.item for c in res.costs] == ["spreader frame"] and res.costs[0].source == "Quote Q-7"


# ------------------------------------------------------------------ revisions, idempotence, persistence
def test_same_inputs_do_not_create_a_new_version():
    st = Store(":memory:")
    a, _ = run(store=st, case_id="c1", target=4)
    b, _ = run(store=st, case_id="c1", target=4)
    assert a.version == b.version == 1 and len(b.history) == 1


def test_revised_document_updates_the_same_decision_with_a_diff():
    st = Store(":memory:")
    log = "Freight elevator capacity: 3,600 kg\nRigging and handling equipment weight per lift: 300 kg\nGeneral notes: synthetic delivery plan."
    heavy = BASE_ALT.replace("Heaviest shipping section: 3,000 kg", "Heaviest shipping section: 4,100 kg")
    first, _ = run(alt=heavy, original=ORIG_SAME, spec=SPEC.replace("5.75", "5.00"), logistics=log, schedule=switchgear(60), target=12, store=st, case_id="rev")
    assert labels(first)["weight:elevator"] == "conclusive" and first.answer == "only_if"
    second = core.decide_and_ask(CaseInput(case_id="rev", revised_documents=[DocumentInput(role="alternate", text=BASE_ALT.replace("Revision: A", "Revision: B"), name="alt_revB.txt", revision="B")]), st)
    assert second.version == 2 and second.diff.from_version == 1
    assert {"key": "weight:elevator", "title": second.diff.changed[0]["title"], "from": "conclusive", "to": "cleared"} == second.diff.changed[0]
    assert second.answer == "yes" and second.diff.answer_before == "only_if"
    assert len(second.history) == 2
    revs = st.document_revisions("rev")
    assert [r["role"] for r in revs].count("alternate") == 2  # both revisions kept, nothing overwritten


def test_persistence_across_store_instances(tmp_path):
    path = str(tmp_path / "k.db")
    st = Store(path)
    run(store=st, case_id="p1", target=4)
    again = Store(path)
    assert again.latest_decision("p1")["answer"] in {"no_not_alone", "only_if", "no"}
    assert again.history("p1")[0]["version"] == 1
    assert again.active_documents("p1")["alternate"].sha256
