"""Regression tests for bugs found by an independent review of the decision, screening, extraction and API code."""
import copy

import pytest

from helpers import BASE_ALT, SCHEDULE, run
from pharos import core, extract as X
from pharos.ingest import parse_bytes
from pharos.schemas import CaseInput, DocumentInput
from pharos.store import Store

FILLER = "\nGeneral notes: data are for review and are synthetic test content only for the regression tests."
ORIG = BASE_ALT.replace("TV-1", "OLD-1").replace("Lead time: 30 weeks ARO", "Lead time: 82 weeks ARO")


def ex(text, role="alternate"):
    return X.extract_document(parse_bytes("t.txt", (text + FILLER).encode(), role))


def labels(res):
    return {f.key: f.label for f in res.findings}


def sched(**over):
    s = copy.deepcopy(SCHEDULE)
    s.update(over)
    return s


# ---------------------------------------------------------------- numbers must never be silently misread
@pytest.mark.parametrize("text,field", [
    ("Total weight: 7.000,5 kg", "total_weight_kg"),
    ("Total weight: 7,5 t", "total_weight_kg"),
    ("Total weight: 7.000 kg", "total_weight_kg"),
    ("Rated capacity: 2.500 kVA", "rated_kva"),
    ("Heat loss: 12,5 kW", "heat_loss_kw"),
    ("Lead time: 3,5 months ARO", "lead_time_weeks"),
])
def test_european_or_ambiguous_number_formats_are_refused_not_misread(text, field):
    assert ex(text)[field].status != "documented"


def test_us_formats_still_read():
    assert ex("Total weight: 7,500 kg")["total_weight_kg"].value == 7500
    assert ex("Rated capacity: 2,500 kVA")["rated_kva"].value == 2500
    assert ex("Total weight: 4,100.5 kg")["total_weight_kg"].value == pytest.approx(4100.5)


def test_lead_time_ignores_transit_and_flags_conflicting_clauses():
    assert ex("Shipment time: 2 weeks transit; lead time 30 weeks ARO")["lead_time_weeks"].value == 30
    fv = ex("Delivery: 12 weeks from receipt of approved drawings; 14 weeks after PO")["lead_time_weeks"]
    assert fv.status == "conflicting"


@pytest.mark.parametrize("text", [
    "Impedance tolerance: 7.5 %", "Impedance: 5.5 - 6.0 %", "Impedance: 5.5 % - 6.0 %",
])
def test_impedance_is_not_taken_from_tolerances_or_ranges(text):
    assert ex(text)["impedance_pct"].status != "documented"


def test_impedance_at_a_load_percentage_is_not_the_load():
    assert ex("Impedance voltage at 100% load: 5.75 %")["impedance_pct"].value == 5.75


# ---------------------------------------------------------------- screening
def test_vector_group_clock_position_change_needs_engineer():
    res, _ = run(original=ORIG, alt=BASE_ALT.replace("Dyn11", "Dyn5"), spec="Winding connection Dyn11\nRated power (ONAN): not less than 2,500 kVA")
    f = next(f for f in res.findings if f.key == "spec:winding")
    assert f.label == "needs_engineer" and "5" in f.summary and "11" in f.summary


def test_alternate_equal_to_original_but_outside_the_spec_band_is_flagged():
    spec = "Impedance 5.75 % (tolerance +/-7.5 %)\nRated power (ONAN): not less than 2,500 kVA"
    res, _ = run(original=ORIG.replace("5.00 %", "5.00 %"), spec=spec)  # both 5.00 %, band is 5.32 to 6.18
    assert labels(res).get("electrical:impedance") == "needs_engineer"


# ---------------------------------------------------------------- decide_and_ask
def test_a_required_item_without_an_arrival_week_is_not_silently_dropped():
    s = sched(items=[{"id": "T1", "name": "Transformer T1", "baseline_arrival_week": 82}, {"id": "SG", "name": "Switchgear"}])
    res, _ = run(original=ORIG, schedule=s, target=10)
    assert res.answer == "needs_data" and any("Switchgear" in m for m in res.missing_project_facts)
    s["items"][1]["requires"] = False
    res, _ = run(original=ORIG, schedule=s, target=10)
    assert res.answer != "needs_data"


def test_missing_order_release_is_stated_as_an_assumption():
    s = sched()
    del s["order_release_week"]
    res, _ = run(original=ORIG, schedule=s, target=4)
    assert any("order release week was not provided" in c for c in res.conditions)


def test_an_alternate_route_only_resolves_the_blockers_it_covers():
    log = "Freight elevator capacity: 2,000 kg\nDelivery door clear opening (W x H): 1,000 x 2,600 mm\nGeneral notes: synthetic."
    s = sched()
    s["items"][1]["arrival_week"] = 60
    s["alternate_routes"] = [{"description": "crane through hatch", "ready_week": 40, "resolves": ["weight:elevator"]}]
    res, _ = run(original=ORIG, logistics=log, schedule=s, target=12)
    assert labels(res)["weight:elevator"] == "conclusive" and labels(res)["dims:door"] == "conclusive"
    assert res.answer == "only_if" and any("unresolved" in c and "door" in c.lower() for c in res.conditions)
    s["alternate_routes"][0].pop("resolves")  # no restriction: documented to cover the physical route
    res, _ = run(original=ORIG, logistics=log, schedule=s, target=12)
    assert not any(c.startswith("unresolved") for c in res.conditions)


def test_impossible_and_negative_targets():
    res, _ = run(original=ORIG, target=200)
    assert res.answer == "no" and "longer than the whole baseline" in res.headline and not res.requirements_to_hit_target
    with pytest.raises(ValueError):
        run(original=ORIG, target=-3)


def test_alternate_later_than_baseline_is_described_as_a_delay():
    res, _ = run(alt=BASE_ALT.replace("30 weeks ARO", "90 weeks ARO"), original=ORIG, schedule=sched(items=[
        {"id": "T1", "name": "Transformer T1", "baseline_arrival_week": 82}, {"id": "SG", "name": "Switchgear", "arrival_week": 10}]))
    assert res.answer == "no_target" and "later" in res.headline and "recover is -" not in res.headline


# ---------------------------------------------------------------- the diff
def test_diff_reports_changed_details_under_an_unchanged_label():
    st = Store(":memory:")
    spec = "Rated power (ONAN): not less than 3,000 kVA"
    first, _ = run(alt=BASE_ALT.replace("2,500 kVA", "2,400 kVA"), original=ORIG, spec=spec, store=st, case_id="d1")
    assert labels(first)["spec:kva"] == "conclusive"
    second = core.decide_and_ask(CaseInput(case_id="d1", revised_documents=[DocumentInput(role="alternate", text=BASE_ALT.replace("2,500 kVA", "2,000 kVA"), name="r.txt", revision="B")]), st)
    assert [u["key"] for u in second.diff.updated] == ["spec:kva"] and "spec:kva" not in second.diff.unchanged_settled


def test_a_new_revision_letter_alone_is_not_a_change():
    st = Store(":memory:")
    spec = "Impedance 5.75 % (tolerance +/-7.5 %)\nRated power (ONAN): not less than 2,500 kVA"
    run(original=ORIG.replace("5.00 %", "5.75 %"), spec=spec, store=st, case_id="d2")
    d = core.decide_and_ask(CaseInput(case_id="d2", revised_documents=[DocumentInput(role="alternate", text=BASE_ALT.replace("Revision: A", "Revision: B"), name="r.txt", revision="B")]), st)
    assert "electrical:impedance" in d.diff.still_open and not d.diff.updated


def test_milestone_moved_even_when_the_difference_is_the_same():
    st = Store(":memory:")
    run(original=ORIG, store=st, case_id="d3", target=4)
    s2 = sched(items=[{"id": "T1", "name": "Transformer T1", "baseline_arrival_week": 92}, {"id": "SG", "name": "Switchgear", "arrival_week": 90, "vendor": "Switchgear vendor"}])
    d = core.decide_and_ask(CaseInput(case_id="d3", project_facts={"schedule": s2}), st)
    assert d.diff.max_recoverable_before == d.diff.max_recoverable_after == 2 and d.diff.milestone_moved is True


# ---------------------------------------------------------------- API path guard
def test_api_path_guard_rejects_sibling_directories_with_the_same_prefix():
    from pharos import api

    assert api._allowed(str(api.SAMPLES / "dev")) is True
    assert api._allowed(str(api.SAMPLES.parent / "samples_evil")) is False
    assert api._allowed(str(api.SAMPLES / ".." / "samples_evil" / "x")) is False
    assert api._allowed("/etc/passwd") is False
