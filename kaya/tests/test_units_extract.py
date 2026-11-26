import pytest

from knockon import extract as X
from knockon import units as U
from knockon.ingest import parse_bytes


FILLER = "\nGeneral notes: data are for submittal review and are synthetic test content only."


def doc(text: str, role: str = "alternate"):
    # pages with almost no text are (correctly) treated as unreadable, so pad single-line snippets
    if "\f" not in text and len(text) < 400:
        text = text + FILLER
    return parse_bytes("t.txt", text.encode(), role)


def field(text: str, name: str, role: str = "alternate"):
    d = doc(text, role)
    return X.extract_document(d)[name]


def test_number_parsing():
    assert U.parse_number("4,100") == 4100
    assert U.parse_number("5.75") == 5.75
    assert U.parse_number("4,10") is None


def test_unit_conversions():
    assert U.weight_to_kg(1000, "lb") == pytest.approx(453.59237)
    assert U.weight_to_kg(1, "t") == 1000
    assert U.weight_to_kg(1, "ton") is None  # ambiguous: short ton vs tonne
    assert U.length_to_mm(83, "in") == pytest.approx(2108.2)
    assert U.pressure_to_kg_m2(250, "psf") == pytest.approx(1220.6, rel=1e-3)
    w, approx = U.time_to_weeks(9, "months")
    assert w == pytest.approx(39.0) and approx
    assert U.time_to_weeks(14, "days") == (2.0, False)


@pytest.mark.parametrize("line,expected", [
    ("Impedance (%Z) at 75 C 5.75 % (tolerance +/-7.5 %)", 5.75),
    ("Percent impedance: 5.00 %", 5.0),
    ("Z% @ 85C . . . . 6.00", 6.0),
    ("Impedance voltage: 5.5 % at 85 C reference.", 5.5),
    ("Short-circuit impedance, uk: 6.00 % (at 85 C ref.)", 6.0),
    ("Impedance 0.0575 pu", 5.75),
])
def test_impedance_variants(line, expected):
    fv = field(line, "impedance_pct")
    assert fv.status == "documented" and fv.value == pytest.approx(expected)
    assert fv.evidence and fv.evidence[0].quote == line and fv.evidence[0].verified


def test_impedance_not_stated_when_no_value():
    fv = field("Impedance: per IEEE C57.12.00 standard values; guaranteed value on request", "impedance_pct")
    assert fv.status == "not_stated"


def test_impedance_tolerance_only_and_zero_sequence_ignored():
    text = "Impedance tolerance +/-7.5 %\nZero sequence impedance 4.1 %"
    assert field(text, "impedance_pct").status == "not_stated"


def test_conflicting_values_are_not_picked():
    fv = field("Impedance: 5.75 %\nPercent impedance: 6.10 %", "impedance_pct")
    assert fv.status == "conflicting" and fv.value is None


def test_unparseable_mention_is_could_not_read_not_not_stated():
    fv = field("Impedance: approximately five and three-quarters 5 3/4 pct", "impedance_pct")
    # a line mentions impedance with digits but no clean value: do not claim "not stated"
    assert fv.status in {"could_not_read", "documented"}


@pytest.mark.parametrize("line,pri,sec", [
    ("Voltage ratio: 13,800 V - 480Y/277 V", 13800, 480),
    ("Voltages: 12.47 kV delta primary / 480Y/277 V grounded wye secondary", 12470, 480),
    ("Rated voltage HV/LV: 13.8 kV / 480Y/277 V", 13800, 480),
    ("Primary voltage 13.8 kV Delta\nSecondary voltage 480Y/277 V", 13800, 480),
    ("The offered unit is rated 2,500 kVA, 13.8 kV / 480Y/277 V.", 13800, 480),
])
def test_voltage_variants(line, pri, sec):
    d = X.extract_document(doc(line))
    assert d["primary_voltage_v"].value == pytest.approx(pri)
    assert d["secondary_voltage_v"].value == pytest.approx(sec)


def test_480_277_is_not_a_ratio():
    d = X.extract_document(doc("Service voltage 480/277 V"))
    assert d["primary_voltage_v"].status != "documented"


@pytest.mark.parametrize("line,sorted_dims,ordered", [
    ("Overall dimensions (L x W x H): 2,100 x 1,500 x 2,200 mm", [1500, 2100, 2200], True),
    ("Overall size (in) L 83 x W 59 x H 87", [1498.6, 2108.2, 2209.8], True),
    ("Dimensions: 2,050 mm (L) x 1,420 mm (W) x 2,150 mm (H)", [1420, 2050, 2150], True),
    ("Dimensions 2,100 x 1,500 x 2,200 mm", [1500, 2100, 2200], False),
])
def test_dimension_variants(line, sorted_dims, ordered):
    fv = field(line, "dimensions_mm")
    assert fv.status == "documented"
    assert fv.detail["sorted_mm"] == pytest.approx(sorted_dims, rel=1e-3)
    assert fv.detail["ordered"] is ordered


def test_weights_sections_and_header_units():
    text = ("Shipping section 1 (core and coil): 4,100 kg\nShipping section 2 (tank): 2,050 kg\nTotal weight (with oil): 7,800 kg")
    d = X.extract_document(doc(text))
    assert d["heaviest_transport_weight_kg"].value == 4100
    assert d["total_weight_kg"].value == 7800
    text2 = "Weight, core and coil - ships separately (lb) 9,040\nTotal weight, filled (lb) 14,800"
    d2 = X.extract_document(doc(text2))
    assert d2["heaviest_transport_weight_kg"].value == pytest.approx(4100.4, rel=1e-3)
    assert d2["total_weight_kg"].value == pytest.approx(6713.2, rel=1e-3)


def test_ambiguous_ton_is_not_converted():
    d = X.extract_document(doc("Heaviest shipping section: 4.5 tons"))
    fv = d["heaviest_transport_weight_kg"]
    assert fv.status != "documented"
    assert any("ambiguous" in n for n in fv.notes)


def test_heat_sum_of_no_load_and_load_loss():
    fv = field("No-load loss: 2.8 kW\nLoad loss: 10.9 kW", "heat_loss_kw")
    assert fv.status == "documented" and fv.value == pytest.approx(13.7)
    assert len(fv.evidence) == 2


def test_lead_time_and_start_condition():
    d = X.extract_document(doc("Lead time: 30 weeks ARO"))
    assert d["lead_time_weeks"].value == 30 and d["lead_time_start"].value == "order"
    d = X.extract_document(doc("Delivery: 36 weeks after approved drawings"))
    assert d["lead_time_start"].value == "approval"
    d = X.extract_document(doc("Delivery: ex-works 26 weeks"))
    assert d["lead_time_weeks"].value == 26 and d["lead_time_start"].status == "not_stated"
    d = X.extract_document(doc("Delivery (ex-works) 9 months after approved submittals"))
    assert d["lead_time_weeks"].value == pytest.approx(39.0)
    assert d["lead_time_weeks"].confidence < 0.9  # months are approximate


def test_not_stated_versus_could_not_read():
    readable_only = doc("Rated capacity: 2,500 kVA\nManufacturer: A\nModel: B")
    assert X.extract_document(readable_only)["impedance_pct"].status == "not_stated"
    with_bad_page = doc("Rated capacity: 2,500 kVA and other text on a readable page here\f \f")
    fv = X.extract_document(with_bad_page)["impedance_pct"]
    assert fv.status == "could_not_read" and fv.unreadable_pages


def test_winding_variants():
    assert field("Vector group: Dyn11", "winding_config").value == "delta-wye"
    assert field("Connection: Delta - Grounded Wye", "winding_config").value == "delta-wye"
    assert field("Phase relationship: Delta-Wye, 30 degree lag", "winding_config").value == "delta-wye"
    assert field("Winding connection: Dd0", "winding_config").value == "delta-delta"


def test_quote_verification():
    assert X.verify_quote("a  b\n c", "a b c")
    assert not X.verify_quote("a b c", "a b d")
