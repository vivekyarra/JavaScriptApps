"""Generate the FINAL hold-out packages (synthetic). Authored after the extractor was frozen (commit b1a83d3).

New layouts and phrasing only. These packages are run exactly once by `pharos-eval --set final`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import sample_lib as S  # noqa: E402
import templates_dev as T  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "samples" / "final"
SYN = "(synthetic sample document - fictional vendor)"


def pdf(path: Path, pages: list[list[tuple]], title: str) -> None:
    S.build_pdf(path, pages, title)


def manifest(d: Path, pid: str, title: str, target: float | None, roles: list[tuple[str, str]], revisions: list[dict] | None = None) -> None:
    m: dict[str, Any] = {"id": pid, "set": "final", "title": title, "documents": [{"role": r, "path": p} for r, p in roles]}
    if target is not None:
        m["recovery_target_weeks"] = target
    if revisions:
        m["revisions"] = revisions
    S.write_json(d / "manifest.json", m)


def main() -> None:
    # ======================================================================= f-01 quayside
    d = ROOT / "f-01-quayside"
    spec = dict(kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr="Illustrative Electric Works (synthetic)", model="IEW-2500-C", rev="C", kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, family="delta-wye",
                dims=(2100, 1500, 2200), sections=[("core and coil", 3900)], total_kg=7600, noload_kw=3.0, load_kw=11.5, lead_max=82, start="order")
    alt_truth = dict(mfr="Quayside Transformers (synthetic)", model="QT-2000-LF", rev="1", kva=2000, pri_v=13800, sec_v=208, z_pct=5.75, family="delta-wye",
                     dims=(2050, 1400, 2100), sections=[("core and coil assembly", 3650)], total_kg=6900, heat_kw=13.8, lead_max=26.0, start="order")
    alt_pages = [[("h", f"OFFER OF SUPPLY {SYN}"),
                  ("p", "Dear Sir or Madam, thank you for your enquiry. We are pleased to offer the unit described below."),
                  ("p", "Offered by: Quayside Transformers (synthetic)"), ("p", "Our reference: QT-2000-LF"), ("p", "Issue 1 of this offer"),
                  ("p", "Offered unit: one three-phase liquid-immersed transformer of 2,000 kVA, with 13,800 V on the high-voltage side and 208Y/120 V on the low-voltage side."),
                  ("p", "The guaranteed impedance is 5.75 per cent. The windings are delta-star connected."),
                  ("p", "Outline size 2050 x 1400 x 2100 mm. The largest piece to be shipped is the core and coil assembly at 3650 kg. Total mass 6900 kg."),
                  ("p", "Losses at rated load: 13.8 kW total."),
                  ("p", "Delivery: 182 days from receipt of PO.")]]
    logi = [[("h", f"SITE ACCESS STATEMENT {SYN}"), ("p", "Issue 3"),
             ("p", "The freight lift is rated for 4,000 kg. The delivery doorway is 1,300 mm wide by 2,300 mm high."),
             ("p", "The slab is designed for 2,500 kg per m2. The room cooling allows 18 kW for this unit.")]]
    sched = {"milestone": {"name": "Energization", "install_test_weeks": 12}, "order_release_week": 0, "submittal_approval_weeks": 4,
             "substituted_item": "T1", "substituted_item_label": "transformer",
             "items": [{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 82, "requires": True},
                       {"id": "SG", "name": "Main switchgear", "arrival_week": 70, "vendor": "Switchgear vendor", "requires": True}],
             "alternate_routes": [{"description": "mobile crane lift through the plant-room hatch", "ready_week": 30, "source": "Quote CR-114"}],
             "remediation": [{"description": "hatch lift", "weeks": 3, "cost": {"amount": 18500, "currency": "USD", "source": "Quote CR-114"}}]}
    pdf(d / "spec.pdf", T.tpl_spec(spec), "f-01 spec")
    pdf(d / "original.pdf", T.tpl_b(orig), "f-01 original")
    pdf(d / "alternate.pdf", alt_pages, "f-01 alternate")
    pdf(d / "logistics.pdf", logi, "f-01 logistics")
    S.write_json(d / "schedule.json", sched)
    manifest(d, "f-01-quayside", "Quayside: alternate below specified kVA and voltage", 8,
             [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf"), ("logistics", "logistics.pdf"), ("schedule", "schedule.json")])
    S.write_json(d / "labels.json", {
        "set": "final",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields({**orig, "heat_kw": 14.5}), "alternate": S.truth_fields(alt_truth)},
        "findings": {"weight:elevator": "not_stated", "weight:slab": "cleared", "dims:door": "conclusive", "heat:cooling": "cleared",
                     "spec:kva": "conclusive", "spec:secondary_voltage": "conclusive"},
        "decision": {"answer": "only_if", "baseline_week": 82, "max_recoverable_weeks": 12, "weeks_earlier_alternate_ships": 56,
                     "controlling_item_alternate": "Main switchgear", "requirements": []}})

    # ======================================================================= f-02 eastgate
    d = ROOT / "f-02-eastgate"
    spec = dict(kva=1600, pri_v=11000, sec_v=433, z_pct=6.0, vec="Dyn11", family="delta-wye", rev="B", tol=7.5)
    orig = dict(mfr="Sample Power Co (synthetic)", model="SPC-1600-D", rev="B", kva=1600, pri_v=11000, sec_v=433, z_pct=6.0, family="delta-wye",
                dims=(2000, 1400, 2000), sections=[("core and coil", 3300)], total_kg=6800, heat_kw=14.0, lead_max=60, start="order")
    alt_truth = dict(mfr="Eastgate Electrical (synthetic)", model="EG-1600", rev="2", kva=1600, pri_v=11000, sec_v=433, family="delta-wye",
                     dims=(2200, 1600, 2300), total_kg=8200, heat_kw=15.1, lead_max=22.0, start=None)
    alt_pages = [[("h", f"EASTGATE ELECTRICAL - TRANSFORMER DATA {SYN}"),
                  ("p", "Vendor name: Eastgate Electrical (synthetic)"), ("p", "Product: EG-1600"), ("p", "Document revision 2"),
                  ("table", [["Parameter", "Value"],
                             ["Rating", "1600 kVA"],
                             ["Voltage (HV / LV)", "11 kV / 433 V"],
                             ["Impedance (%)", "6.00"],
                             ["Vector group", "Dyn11"],
                             ["Overall dimensions (mm)", "L 2200   W 1600   H 2300"],
                             ["Total mass (kg)", "8,200"],
                             ["Total loss (kW)", "15.1"],
                             ["Delivery period", "20-22 weeks"]], [200, 280])],
                 [("h", "Guarantees"), ("p", "Guaranteed impedance 6.50 % at rated tap, subject to standard tolerance.")]]
    logi = [[("h", f"SITE LIMITS {SYN}"), ("p", "Issue 1"),
             ("table", [["Item", "Value"], ["Goods lift safe working load", "4,000 kg"], ["Floor loading limit", "3,500 kg per m2"],
                        ["Plant room doorway (W x H)", "2,100 x 2,400 mm"], ["Cooling available for equipment heat", "20 kW"]], [260, 220])]]
    sched = {"milestone": {"name": "Energization", "install_test_weeks": 10}, "order_release_week": 0, "submittal_approval_weeks": 5,
             "substituted_item": "T1", "substituted_item_label": "transformer",
             "items": [{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 60, "requires": True},
                       {"id": "SG", "name": "Main switchgear", "arrival_week": 64, "vendor": "Switchgear vendor", "requires": True}]}
    pdf(d / "spec.pdf", T.tpl_spec(spec), "f-02 spec")
    pdf(d / "original.pdf", T.tpl_a(orig), "f-02 original")
    pdf(d / "alternate.pdf", alt_pages, "f-02 alternate")
    pdf(d / "logistics.pdf", logi, "f-02 logistics")
    S.write_json(d / "schedule.json", sched)
    manifest(d, "f-02-eastgate", "Eastgate: conflicting impedance, total mass only, start condition missing", 3,
             [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf"), ("logistics", "logistics.pdf"), ("schedule", "schedule.json")])
    alt_fields = S.truth_fields(alt_truth)
    alt_fields["impedance_pct"] = {"status": "conflicting"}
    S.write_json(d / "labels.json", {
        "set": "final",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields({k: v for k, v in orig.items() if k != "family"}), "alternate": alt_fields},
        "findings": {"weight:elevator": "not_stated", "weight:slab": "cleared", "dims:door": "cleared", "heat:cooling": "cleared", "electrical:impedance": "not_stated"},
        "decision": {"answer": "no_not_alone", "baseline_week": 64, "max_recoverable_weeks": 0, "weeks_earlier_alternate_ships": 40,
                     "controlling_item_alternate": "Main switchgear", "requirements": [{"item": "Main switchgear", "must_be_ready_by_week": 61}]}})

    # ======================================================================= f-03 northfield
    d = ROOT / "f-03-northfield"
    spec = dict(kva=2000, pri_v=12470, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr="Example Transformers Ltd (synthetic)", model="SYN-2000-E", rev="D", kva=2000, pri_v=12470, sec_v=480, z_pct=5.75, family="delta-wye",
                dims=(2000, 1400, 2100), sections=[("core and coil", 3500)], total_kg=7100, heat_kw=12.5, lead_max=70, start="order")
    alt_truth = dict(mfr="Northfield Power (synthetic)", model="NP-2000-OF", rev="1", kva=2000, pri_v=12470, sec_v=480, z_pct=5.75, family="delta-wye",
                     heat_kw=12.309, lead_max=30.333, start="order")
    alt_pages = [[("h", f"NORTHFIELD POWER - PRODUCT SUMMARY {SYN}"),
                  ("p", "Maker: Northfield Power (synthetic)"), ("p", "Item: NP-2000-OF"), ("p", "Rev 1"),
                  ("p", "• Rating ........ 2.0 MVA"),
                  ("p", "• HV / LV ....... 12.47 kV / 480Y/277 V"),
                  ("p", "• %Z (pu) ....... 0.0575 pu"),
                  ("p", "• Group ......... Dyn11"),
                  ("p", "• Heaviest shipping piece: 4.6 tons"),
                  ("p", "• Complete unit weight ....... 9.6 tons"),
                  ("p", "• Heat dissipation ....... 42,000 BTU/h"),
                  ("p", "• Lead time ....... 7 months ARO")]]
    logi = [[("h", f"SITE SUMMARY {SYN}"), ("p", "Issue 2"),
             ("p", "• Service elevator capacity 3,000 kg"), ("p", "• Floor loading 2,000 kg/m2"),
             ("p", "• Cooling allowance 14 kW"), ("p", "• Overhead clearance 10 ft")]]
    sched = {"milestone": {"name": "Energization", "install_test_weeks": 12}, "order_release_week": 0, "submittal_approval_weeks": 4,
             "substituted_item": "T1", "substituted_item_label": "transformer",
             "items": [{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 70, "requires": True},
                       {"id": "SG", "name": "Main switchgear", "arrival_week": 60, "vendor": "Switchgear vendor", "requires": True}]}
    pdf(d / "spec.pdf", T.tpl_spec(spec), "f-03 spec")
    pdf(d / "original.pdf", T.tpl_a(orig), "f-03 original")
    pdf(d / "alternate.pdf", alt_pages, "f-03 alternate")
    pdf(d / "logistics.pdf", logi, "f-03 logistics")
    S.write_json(d / "schedule.json", sched)
    manifest(d, "f-03-northfield", "Northfield: weights in ambiguous tons, BTU/h heat, per-unit impedance", 6,
             [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf"), ("logistics", "logistics.pdf"), ("schedule", "schedule.json")])
    S.write_json(d / "labels.json", {
        "set": "final",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields({k: v for k, v in orig.items() if k != "family"}), "alternate": S.truth_fields(alt_truth)},
        "findings": {"weight:elevator": "not_stated", "weight:slab": "not_stated", "dims:ceiling": "not_stated", "heat:cooling": "cleared"},
        "decision": {"answer": "only_if", "baseline_week": 70, "max_recoverable_weeks": 10, "weeks_earlier_alternate_ships": 39.67,
                     "controlling_item_alternate": "Main switchgear", "requirements": []}})

    # ======================================================================= f-04 southport (documents only + revision)
    d = ROOT / "f-04-southport"
    spec = dict(kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr="Example Transformers Ltd (synthetic)", model="SYN-2500-F", rev="A", kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, family="delta-wye",
                dims=(2100, 1500, 2200), sections=[("core and coil", 3900)], total_kg=7600, heat_kw=14.8, lead_max=82, start="order")
    alt_truth = dict(mfr="Southport Electric (synthetic)", model="SE-2500", rev="A", kva=2500, pri_v=13800, sec_v=480, family="delta-wye",
                     dims=(2100, 1500, 2200), sections=[("heaviest", 3800)], lead_max=40.0, start=None)

    def southport(rev: str, with_z: bool) -> list[list[tuple]]:
        lines: list[tuple] = [("h", f"SOUTHPORT ELECTRIC - DATA SUMMARY {SYN}"), ("p", "producer = Southport Electric (synthetic)"), ("p", "designation = SE-2500"),
                              ("p", f"revision = {rev}"), ("p", "capacity = 2500 kVA"), ("p", "voltage = 13.8 kV / 480Y/277 V"), ("p", "connection = Dyn11")]
        if with_z:
            lines.append(("p", "impedance = 5.75 %"))
        lines += [("p", "size = 2100x1500x2200 mm"), ("p", "heaviest piece = 3,800 kg"), ("p", "delivery = 40 weeks")]
        return [lines]

    pdf(d / "spec.pdf", T.tpl_spec(spec), "f-04 spec")
    pdf(d / "original.pdf", T.tpl_a(orig), "f-04 original")
    pdf(d / "alternate.pdf", southport("A", False), "f-04 alternate")
    pdf(d / "alternate_revB.pdf", southport("B", True), "f-04 alternate rev B")
    manifest(d, "f-04-southport", "Southport: documents only (no schedule, no site limits); %Z missing then supplied", 6,
             [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf")],
             [{"label": "B", "documents": [{"role": "alternate", "path": "alternate_revB.pdf", "revision": "B"}]}])
    S.write_json(d / "labels.json", {
        "set": "final",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields({k: v for k, v in orig.items() if k != "family"}), "alternate": S.truth_fields({k: v for k, v in alt_truth.items()}, unreadable=set())},
        "findings": {"electrical:impedance": "not_stated"},
        "decision": {"answer": "needs_data"},
        "revision": {"removed": ["electrical:impedance"], "answer_after": "needs_data"}})
    print("generated final samples")


if __name__ == "__main__":
    main()
