"""check_submittal: per-requirement verdicts with the requirement and the supplier's evidence paired."""
import pytest

from pharos import core
from pharos.schemas import CaseInput, DocumentInput
from pharos.store import Store

SPEC_TX = """Rated power (ONAN): not less than 2,500 kVA
Primary voltage 13.8 kV, delta
Secondary voltage 480Y/277 V
Impedance 5.75 % (tolerance +/-7.5 %)
Total losses: 15.0 kW maximum
Winding connection Dyn11
"""
SUB_TX = """Manufacturer: Test Vendor (synthetic)
Model: TV-2500
Revision: A
Rated capacity: 2,500 kVA
Voltage ratio: 13,800 V - 480Y/277 V
Impedance (%Z) at 75 C: 5.80 %
Vector group: Dyn11
Total losses: 16.2 kW
"""
SPEC_SG = """Rated maximum voltage: 15 kV
Rated continuous current: 1200 A
Short-circuit rating: not less than 40 kA
BIL: 95 kV
Enclosure: NEMA 3R
Frequency: 60 Hz
"""
SUB_SG = """Manufacturer: Test Switchgear Co (synthetic)
Model: TS-15
Rated maximum voltage: 15 kV
Rated continuous current: 2000 A
Interrupting rating: 31.5 kA rms symmetrical
BIL: 95 kV
Enclosure: NEMA 3R
"""


def check(spec, sub, **kw):
    inp = CaseInput(documents=[DocumentInput(role="spec", text=spec, name="spec.txt"), DocumentInput(role="alternate", text=sub, name="sub.txt")], **kw)
    return core.check_submittal(inp, Store(":memory:"))


def by(res):
    return {r.field: r for r in res.requirements}


def test_works_with_only_a_spec_and_a_submittal():
    res = check(SPEC_TX, SUB_TX)
    r = by(res)
    assert r["rated_kva"].verdict == "complies" and r["primary_voltage_v"].verdict == "complies"
    assert r["winding_config"].verdict == "complies"
    assert res.counts["complies"] >= 4


def test_deviation_is_cited_on_both_sides_with_the_basis():
    r = by(check(SPEC_TX, SUB_TX))
    loss = r["heat_loss_kw"]
    assert loss.verdict == "deviates" and loss.basis == "at most 15 kW"
    assert loss.requirement_evidence[0].document == "spec.txt" and "15.0 kW maximum" in loss.requirement_evidence[0].quote
    assert loss.submittal_evidence[0].document == "sub.txt" and "16.2 kW" in loss.submittal_evidence[0].quote
    assert loss.requirement == 15 and loss.submittal_value == 16.2
    # impedance 5.80 is inside 5.75 +/- 7.5 %
    assert r["impedance_pct"].verdict == "complies"


def test_missing_says_where_it_looked_and_what_for():
    r = by(check(SPEC_TX, SUB_TX.replace("Total losses: 16.2 kW\n", "")))
    m = r["heat_loss_kw"]
    assert m.verdict == "missing" and m.submittal_evidence == []
    assert m.searched["document"] == "sub.txt" and m.searched["readable_pages"] == [1] and m.searched["unreadable_pages"] == []
    assert "heat" in m.searched["looking_for"].lower() or "loss" in m.searched["looking_for"].lower()


def test_an_unreadable_page_is_not_reported_as_missing():
    r = by(check(SPEC_TX, SUB_TX.replace("Total losses: 16.2 kW\n", "") + "\f \f"))
    assert r["heat_loss_kw"].verdict == "unreadable" and r["heat_loss_kw"].searched["unreadable_pages"] == [2, 3] or r["heat_loss_kw"].searched["unreadable_pages"]


def test_conflicting_submittal_values():
    r = by(check(SPEC_TX, SUB_TX + "Percent impedance: 6.30 %\n"))
    assert r["impedance_pct"].verdict == "conflicting"


def test_conflicting_specification_is_reported_not_resolved():
    r = by(check(SPEC_TX + "Percent impedance: 6.30 %\n", SUB_TX))
    assert r["impedance_pct"].verdict == "conflicting" and "specification" in r["impedance_pct"].basis


def test_switchgear_capability_requirements_read_as_minimums():
    res = check(SPEC_SG, SUB_SG)
    r = by(res)
    assert res.equipment_type == "switchgear"
    assert r["continuous_current_a"].verdict == "complies" and "minimum" in r["continuous_current_a"].basis  # 2000 A offered against 1200 A
    assert r["short_circuit_ka"].verdict == "deviates"                       # 31.5 kA against a 40 kA minimum
    assert r["bil_kv"].verdict == "complies" and r["nema_type"].verdict == "complies" and r["rated_voltage_kv"].verdict == "complies"
    assert r["frequency_hz"].verdict == "missing"


def test_wrong_column_trap_in_a_submittal_table():
    table = "Catalogue (synthetic)\nModel TS-15A TS-15B TS-15C\nRated continuous current (A) 1200 2000 3000\nInterrupting rating (kA) 25 31.5 40\n"
    sub = "Manufacturer: Test Switchgear Co (synthetic)\n" + table
    good = by(check(SPEC_SG, sub, offered_model="TS-15C"))
    assert good["continuous_current_a"].verdict == "complies" and good["short_circuit_ka"].verdict == "complies"
    assert "TS-15C" in good["short_circuit_ka"].submittal_evidence[0].quote
    wrong = check(SPEC_SG, sub, offered_model="TS-15A")
    assert by(wrong)["short_circuit_ka"].verdict == "deviates"      # 25 kA, the offered model's own value
    none = check(SPEC_SG, sub)
    assert by(none)["short_circuit_ka"].verdict == "conflicting"    # never the first number on the row
    assert none.table_warnings and "TS-15A" in none.table_warnings[0]


def test_both_documents_are_required():
    with pytest.raises(ValueError):
        core.check_submittal(CaseInput(documents=[DocumentInput(role="alternate", text=SUB_TX, name="s.txt")]), Store(":memory:"))
    with pytest.raises(ValueError):
        core.check_submittal(CaseInput(documents=[DocumentInput(role="spec", text=SPEC_TX, name="s.txt")]), Store(":memory:"))


def test_a_maximum_is_a_ceiling_not_an_exact_value():
    spec = "Total losses: 15.0 kW maximum\nRated power (ONAN): not less than 2,500 kVA\n"
    lower = by(check(spec, SUB_TX.replace("16.2 kW", "14.0 kW")))["heat_loss_kw"]
    assert lower.verdict == "complies" and lower.basis == "at most 15 kW"
    assert by(check(spec, SUB_TX.replace("16.2 kW", "15.0 kW")))["heat_loss_kw"].verdict == "complies"
    assert by(check(spec, SUB_TX))["heat_loss_kw"].verdict == "deviates"
    kva = by(check(spec, SUB_TX.replace("2,500 kVA", "3,000 kVA")))["rated_kva"]
    assert kva.verdict == "complies"  # 'not less than' is a floor
