from pharos import core
from pharos.schemas import CaseInput, DocumentInput
from pharos.store import Store

SPEC = """Manufacturer: Original Maker (synthetic)
Model: OM-1
Rated capacity: 2,500 kVA
Voltage ratio: 13,800 V - 480Y/277 V
Impedance (%Z) at 75 C: 5.75 % +/- 7.5 %
Vector group: Dyn11
Total losses: maximum 14.0 kW
"""

CSV = """manufacturer,model,rated_kva,primary_voltage_v,secondary_voltage_v,impedance_pct,winding_config,heat_loss_kw,lead_time_weeks
Alpha Fictional,AF-2500,2500,13800,480,5.8,Dyn11,12.5,26
Beta Fictional,BF-2000,2000,13800,480,5.8,Dyn11,11.0,20
Gamma Fictional,GF-2500,2500,13800,480,,Dyn11,13.0,30
Original Maker,OM-1,2500,13800,480,5.75,Dyn11,12.0,60
"""


def run(spec, *libs):
    docs = [DocumentInput(role="spec", text=spec, name="spec.txt")]
    docs += [DocumentInput(role="library", text=t, name=n) for n, t in libs]
    return core.find_alternatives(CaseInput(documents=docs), Store(":memory:"))


def test_csv_library_ranks_and_excludes_original():
    r = run(SPEC, ("lib.csv", CSV))
    models = {c.model: c for c in r.candidates}
    assert models["AF-2500"].verdict == "supported"
    assert models["BF-2000"].verdict == "falls_short"
    assert models["GF-2500"].verdict == "needs_confirmation"
    assert r.candidates[0].model == "AF-2500"
    assert not r.none_supported
    assert models["AF-2500"].requirements[0].submittal_evidence[0].quote.startswith("Alpha Fictional")


def test_none_supported_when_nothing_meets():
    r = run(SPEC, ("lib.csv", CSV.split("\n")[0] + "\nBeta Fictional,BF-2000,2000,13800,480,5.8,Dyn11,11.0,20\n"))
    assert r.none_supported
    assert r.candidates[0].verdict == "falls_short"


def test_no_library_proposes_nothing():
    r = run(SPEC)
    assert r.candidates == [] and r.none_supported
    assert "No library" in r.summary
