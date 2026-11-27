"""Regression tests for every gap the final hold-out exposed (first run recorded in eval/results/final.json).

The final set is no longer a hold-out once its failures were fixed; these tests keep the fixes honest.
"""
import io
from pathlib import Path

import pytest

from pharos import extract as X
from pharos.ingest import parse_bytes

FILLER = "\nGeneral notes: data are for review and are synthetic test content only for the regression tests."


def doc(text: str, role: str = "alternate"):
    return parse_bytes("t.txt", (text + FILLER).encode(), role)


def fields(text: str, role: str = "alternate"):
    return X.extract_document(doc(text, role))


def test_per_cent_and_percent_in_parentheses_before_the_value():
    assert fields("The guaranteed impedance is 5.75 per cent.")["impedance_pct"].value == pytest.approx(5.75)
    assert fields("Impedance (%)    6.00")["impedance_pct"].value == pytest.approx(6.0)


def test_two_lines_with_different_impedance_are_conflicting_not_silently_picked():
    fv = fields("Impedance (%)    6.00\nGuaranteed impedance 6.50 % at rated tap")["impedance_pct"]
    assert fv.status == "conflicting" and fv.value is None


def test_unparsed_second_mention_lowers_confidence():
    fv = fields("Percent impedance: 5.75 %\nImpedance at minimum tap is five point five pct (5.5 pct)")["impedance_pct"]
    assert fv.status == "documented"
    assert any("could not be parsed" in n for n in fv.notes) and fv.confidence <= 0.5


def test_losses_with_total_at_the_end():
    assert fields("Losses at rated load: 13.8 kW total.")["heat_loss_kw"].value == pytest.approx(13.8)


def test_door_wide_by_high_feet_and_allowance():
    d = X.extract_document(doc("The delivery doorway is 1,300 mm wide by 2,300 mm high.", "logistics"))
    assert d["door_width_mm"].value == 1300 and d["door_height_mm"].value == 2300
    d = X.extract_document(doc("Cooling allowance 14 kW\nOverhead clearance 10 ft", "logistics"))
    assert d["cooling_capacity_kw"].value == 14
    assert d["ceiling_clearance_mm"].value == pytest.approx(3048)


def test_letter_labelled_dimensions_without_x():
    fv = fields("Overall dimensions (mm)    L 2200   W 1600   H 2300")["dimensions_mm"]
    assert fv.status == "documented" and fv.value == {"length": 2200, "width": 1600, "height": 2300}


def test_identity_labels():
    d = fields("Offered by: Quayside Transformers (synthetic)\nOur reference: QT-2000-LF")
    assert d["manufacturer"].value.startswith("Quayside") and d["model"].value == "QT-2000-LF"
    d = fields("producer = Southport Electric (synthetic)\ndesignation = SE-2500")
    assert d["manufacturer"].value.startswith("Southport") and d["model"].value == "SE-2500"


def test_bare_iec_vector_group_line():
    assert fields("Group ......... Dyn11")["winding_config"].value == "delta-wye"


def test_bullet_glyphs_do_not_make_a_page_unreadable():
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 700
    for line in ["NORTHFIELD POWER - PRODUCT SUMMARY (synthetic sample document)", "• Rating ........ 2.0 MVA",
                 "• HV / LV ....... 12.47 kV / 480Y/277 V", "• %Z (pu) ....... 0.0575 pu",
                 "• Heat dissipation ....... 42,000 BTU/h", "• Lead time ....... 7 months ARO"]:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    d = parse_bytes("bul.pdf", buf.getvalue(), "alternate")
    assert d.pages[0].status == "ok"
    f = X.extract_document(d)
    assert f["rated_kva"].value == 2000 and f["primary_voltage_v"].value == 12470 and f["secondary_voltage_v"].value == 480
    assert f["impedance_pct"].value == pytest.approx(5.75)
    assert f["heat_loss_kw"].value == pytest.approx(12.309, rel=1e-3)
    assert f["lead_time_weeks"].value == pytest.approx(30.333, rel=1e-3)


def test_genuinely_garbled_page_is_still_unreadable():
    garbled = " ".join(["(cid:12)(cid:45)"] * 30)
    d = parse_bytes("g.txt", garbled.encode(), "alternate")
    assert d.pages[0].status == "unreadable"
