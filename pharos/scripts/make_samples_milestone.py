"""Generate the two unfamiliar MILESTONE packages (synthetic)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import sample_lib as S  # noqa: E402
import templates_dev as T  # noqa: E402
import templates_milestone as M  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "samples" / "milestone"


def main() -> None:
    # ------------------------------------------------------------ m-01 harbor: documented constraints
    d = ROOT / "m-01-harbor"
    spec = dict(kva=1500, pri_v=12470, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr="Example Transformers Ltd (synthetic)", model="SYN-1500-A", rev="B", kva=1500, pri_v=12470, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye",
                dims=(2000, 1400, 2100), sections=[("core and coil", 3900)], total_kg=6300, heat_kw=11.2, lead_max=70, start="order")
    alt = dict(mfr="Harbor Electric (synthetic)", model="HE-1500-DY-2", rev="C", kva=1500, pri_v=12470, sec_v=480, z_pct=6.0, family="delta-wye",
               dims=(2108.2, 1498.6, 2209.8), sections=[("core and coil", 4100.4)], total_kg=6713.2, heat_kw=11.9, lead_max=39.0, start="approval",
               disp={"pri": "12.47 kV", "size": "L 83 x W 59 x H 87", "heaviest": "9,040", "total": "14,800", "lead": "9 months after approved submittals"})
    alt_b = {**alt, "rev": "D", "sections": [("core and coil", 2721.6)], "disp": {**alt["disp"], "heaviest": "6,000"}}
    sched = {"milestone": {"name": "Energization", "install_test_weeks": 10}, "order_release_week": 0, "submittal_approval_weeks": 6,
             "substituted_item": "T1", "substituted_item_label": "transformer",
             "items": [{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 70, "requires": True},
                       {"id": "SG1", "name": "Switchgear lineup SG-1", "arrival_week": 72, "vendor": "Switchgear vendor", "requires": True}]}
    S.build_pdf(d / "spec.pdf", T.tpl_spec(spec), "m-01 spec")
    S.build_pdf(d / "original.pdf", T.tpl_a(orig), "m-01 original")
    S.build_pdf(d / "alternate.pdf", M.tpl_harbor(alt), "m-01 alternate")
    S.build_pdf(d / "alternate_revD.pdf", M.tpl_harbor(alt_b), "m-01 alternate rev D")
    S.build_pdf(d / "logistics.pdf", M.tpl_harbor_logistics({}), "m-01 logistics")
    S.write_json(d / "schedule.json", sched)
    S.write_json(d / "manifest.json", {
        "id": "m-01-harbor", "set": "milestone", "title": "Harbor campus: transformer T1 alternate (imperial units)", "recovery_target_weeks": 3,
        "documents": [{"role": r, "path": p} for r, p in [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf"), ("logistics", "logistics.pdf"), ("schedule", "schedule.json")]],
        "revisions": [{"label": "D", "documents": [{"role": "alternate", "path": "alternate_revD.pdf", "revision": "D"}]}]})
    S.write_json(d / "labels.json", {
        "set": "milestone",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields(orig), "alternate": S.truth_fields(alt)},
        "findings": {"weight:elevator": "conclusive", "weight:slab": "conclusive", "dims:door": "cleared", "heat:cooling": "cleared", "electrical:impedance": "needs_engineer"},
        "decision": {"answer": "no_not_alone", "baseline_week": 72, "max_recoverable_weeks": 0, "weeks_earlier_alternate_ships": 25,
                     "controlling_item_alternate": "Switchgear lineup SG-1", "requirements": [{"item": "Switchgear lineup SG-1", "must_be_ready_by_week": 69}]},
        "revision": {"changed": {"weight:elevator": ["conclusive", "cleared"]}, "still_open": ["electrical:impedance"], "milestone_moved": False, "answer_after": "no_not_alone"}})

    # ------------------------------------------------------------ m-02 meridian: genuine unknowns
    d = ROOT / "m-02-meridian"
    spec = dict(kva=2000, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr="Illustrative Electric Works (synthetic)", model="IEW-2000-B", rev="A", kva=2000, pri_v=13800, sec_v=480, z_pct=5.75, family="delta-wye",
                dims=(2000, 1400, 2100), sections=[("core and coil", 3500)], total_kg=6900, noload_kw=2.8, load_kw=10.9, lead_max=88, start="order")
    alt_unreadable = dict(mfr="Meridian Power Systems (synthetic)", model="MPS-2000-LF", rev="2", kva=2000, pri_v=13800, sec_v=480, family="delta-wye",
                          dims=(2050, 1420, 2150), sections=[("heaviest", 3950)], total_kg=7400, heat_kw=13.2, lead_max=26, start=None)
    alt_rev = {**alt_unreadable, "rev": "3", "z_pct": 5.75, "start": "order"}
    sched = {"milestone": {"name": "Energization", "install_test_weeks": 12}, "order_release_week": 0, "submittal_approval_weeks": 4,
             "substituted_item": "T1", "substituted_item_label": "transformer",
             "items": [{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 88, "requires": True},
                       {"id": "SG1", "name": "Switchgear lineup SG-1", "arrival_week": 60, "vendor": "Switchgear vendor", "requires": True}]}
    S.build_pdf(d / "spec.pdf", T.tpl_spec(spec), "m-02 spec")
    S.build_pdf(d / "original.pdf", T.tpl_b(orig), "m-02 original")
    S.build_pdf_with_scanned_pages(d / "alternate.pdf", M.tpl_meridian(alt_unreadable, scanned_weights=True), {3}, "m-02 alternate")
    S.build_pdf(d / "alternate_rev3.pdf", M.tpl_meridian(alt_rev, scanned_weights=False), "m-02 alternate rev 3")
    S.build_pdf(d / "logistics.pdf", M.tpl_meridian_logistics({}), "m-02 logistics")
    S.write_json(d / "schedule.json", sched)
    S.write_json(d / "manifest.json", {
        "id": "m-02-meridian", "set": "milestone", "title": "Meridian plant: transformer T1 alternate (scanned weights page, no %Z)", "recovery_target_weeks": 20,
        "documents": [{"role": r, "path": p} for r, p in [("spec", "spec.pdf"), ("original", "original.pdf"), ("alternate", "alternate.pdf"), ("logistics", "logistics.pdf"), ("schedule", "schedule.json")]],
        "revisions": [{"label": "3", "documents": [{"role": "alternate", "path": "alternate_rev3.pdf", "revision": "3"}]}]})
    unread = {"heaviest_transport_weight_kg", "total_weight_kg", "heat_loss_kw"}
    S.write_json(d / "labels.json", {
        "set": "milestone",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields({**orig, "heat_kw": 13.7}),
                   "alternate": S.truth_fields({k: v for k, v in alt_unreadable.items() if k != "z_pct"}, unreadable=unread | {"impedance_pct", "shipping_total_weight_kg"})},
        "findings": {"weight:elevator": "could_not_read", "weight:slab": "could_not_read", "heat:cooling": "could_not_read", "dims:door": "cleared",
                     "dims:ceiling": "cleared", "electrical:impedance": "could_not_read"},
        "decision": {"answer": "only_if", "baseline_week": 88, "max_recoverable_weeks": 28, "weeks_earlier_alternate_ships": 62,
                     "controlling_item_alternate": "Switchgear lineup SG-1", "requirements": []},
        "revision": {"changed": {"weight:elevator": ["could_not_read", "cleared"], "weight:slab": ["could_not_read", "cleared"], "heat:cooling": ["could_not_read", "cleared"]},
                     "removed": ["electrical:impedance"], "milestone_moved": False, "answer_after": "yes"}})
    print("generated milestone samples")


if __name__ == "__main__":
    main()
