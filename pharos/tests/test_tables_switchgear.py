"""The wrong-column trap, switchgear fields, and regression lines taken from real public datasheets."""
import io

import pytest

from pharos import extract as X
from pharos.ingest import parse_bytes

FILLER = "\nGeneral notes: data are for review and are synthetic test content only for the regression tests."

CATALOG = """Pad-mount transformer catalogue (synthetic sample document)
Model SYN-1000 SYN-1500 SYN-2000
Rated power (kVA) 1000 1500 2000
Impedance (%) 5.50 5.75 6.00
Total weight (kg) 3200 4100 5200
Heat loss (kW) 9.0 12.5 15.5
"""


def ex(text, offered=None, role="alternate"):
    return X.extract_document(parse_bytes("t.txt", (text + FILLER).encode(), role), offered)


def test_the_offered_models_column_is_used_not_the_first_number():
    f = ex(CATALOG, "SYN-1500")
    assert f["rated_kva"].value == 1500 and f["impedance_pct"].value == 5.75
    assert f["total_weight_kg"].value == 4100 and f["heat_loss_kw"].value == 12.5
    ev = f["rated_kva"].evidence[0]
    assert ev.verified and "SYN-1500" in ev.quote and "1000 1500 2000" in ev.quote  # the cited row is the original table row
    assert any("read column 'SYN-1500'" in n for n in f["rated_kva"].notes)


def test_a_different_offered_model_gives_that_models_values():
    f = ex(CATALOG, "SYN-2000")
    assert f["rated_kva"].value == 2000 and f["total_weight_kg"].value == 5200


def test_without_an_offered_model_the_table_is_withheld_and_fields_conflict():
    f = ex(CATALOG, None)
    for name in ("rated_kva", "impedance_pct", "total_weight_kg", "heat_loss_kw"):
        assert f[name].status == "conflicting" and f[name].value is None, name
        assert "offered model is not identified" in " ".join(f[name].notes)


def test_an_offered_model_that_is_not_in_the_table_is_not_guessed():
    f = ex(CATALOG, "SYN-9999")
    assert f["rated_kva"].status == "conflicting"


def test_the_documents_own_model_line_selects_the_column():
    f = ex("Model: SYN-1500\n" + CATALOG)
    assert f["rated_kva"].value == 1500


def test_rating_headers_select_by_kva():
    text = "Ratings table\nkVA 750 1000 1500\nImpedance (%) 5.50 5.75 6.00\nTotal weight (kg) 2600 3200 4100\n"
    assert ex(text, "1000 kVA")["impedance_pct"].value == 5.75
    assert ex(text, "1000 kVA")["total_weight_kg"].value == 3200


def test_a_rating_list_in_a_weight_header_is_not_a_weight():
    # a real public transformer data sheet header: the trailing numbers are kVA ratings
    assert ex("kVA Height Flange - Flange Depth Total Weight (Lb) 225 1500 7500")["total_weight_kg"].status != "documented"


@pytest.mark.parametrize("line", [
    "System Voltage and Below; Low Voltage, 15kV",
    "Up to 34,500 V Delta or Wye connected high voltage",
    "secondary voltages not exceeding 700V are 45-3,750 kVA",
])
def test_voltage_ranges_ceilings_and_classes_are_not_unit_voltages(line):
    f = ex(line)
    assert f["primary_voltage_v"].status != "documented" and f["secondary_voltage_v"].status != "documented"


def test_a_tolerance_threshold_is_not_an_impedance():
    assert ex("7.5% of nominal value for impedance values greater than 2.5%")["impedance_pct"].status != "documented"


def test_a_control_power_transformer_does_not_make_switchgear_a_transformer():
    docs = [parse_bytes("s.txt", ("Metal-clad switchgear, 15 kV class.\nMax CPT is 15kVA in draw out.\nMetal-clad switchgear assemblies." + FILLER).encode(), "alternate")]
    assert X.detect_equipment_type(docs) == "switchgear"


def test_switchgear_fields():
    f = ex("Rated maximum voltage: 15 kV\nRated continuous current: 1200 A\nMain bus rating: 3000 A\n"
           "Short-circuit rating: 40 kA rms symmetrical\nBIL: 95 kV\nEnclosure: NEMA 3R\nFrequency: 60 Hz")
    assert f["rated_voltage_kv"].value == 15 and f["continuous_current_a"].value == 1200 and f["main_bus_a"].value == 3000
    assert f["short_circuit_ka"].value == 40 and f["bil_kv"].value == 95 and f["nema_type"].value == "3R" and f["frequency_hz"].value == 60


def test_an_option_list_is_not_a_single_value():
    f = ex("Rated continuous current: 1200, 2000 and 3000A\nInterrupting rating options: 40, 50 or 63 kA")
    assert f["continuous_current_a"].status != "documented" and f["short_circuit_ka"].status != "documented"


def test_a_real_pdf_with_a_ruled_table():
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 720
    for line in ["Catalogue sheet (synthetic)", "Model SYN-1000 SYN-1500 SYN-2000", "Rated power (kVA) 1000 1500 2000", "Impedance (%) 5.50 5.75 6.00"]:
        c.drawString(72, y, line); y -= 18
    c.save()
    d = parse_bytes("c.pdf", buf.getvalue(), "alternate")
    f = X.extract_document(d, "SYN-1500")
    assert f["rated_kva"].value == 1500 and f["impedance_pct"].value == 5.75 and f["rated_kva"].evidence[0].verified
