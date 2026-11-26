"""Generate the DEVELOPMENT sample packages (synthetic). Milestone and final sets have their own scripts."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import sample_lib as S  # noqa: E402
import templates_dev as T  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "samples" / "dev"

VENDOR_A = "Example Transformers Ltd (synthetic)"
VENDOR_B = "Sample Power Co (synthetic)"
VENDOR_C = "Illustrative Electric Works (synthetic)"


def schedule_json(**kw: Any) -> dict[str, Any]:
    return kw


def write_package(pid: str, title: str, docs: dict[str, tuple], logistics: dict[str, Any], schedule: dict[str, Any], target: float,
                  labels: dict[str, Any], revision: dict[str, Any] | None = None) -> None:
    d = ROOT / pid
    manifest_docs = []
    for role, (fn, data, name) in docs.items():
        S.build_pdf(d / name, fn(data), title=f"{pid} {role}")
        manifest_docs.append({"role": role, "path": name})
    S.build_pdf(d / "logistics.pdf", T.tpl_logistics(logistics), title=f"{pid} logistics")
    manifest_docs.append({"role": "logistics", "path": "logistics.pdf"})
    S.write_json(d / "schedule.json", schedule)
    manifest_docs.append({"role": "schedule", "path": "schedule.json"})
    manifest: dict[str, Any] = {"id": pid, "set": "dev", "title": title, "recovery_target_weeks": target, "documents": manifest_docs}
    if revision:
        rdocs = []
        for role, (fn, data, name, rev) in revision["docs"].items():
            S.build_pdf(d / name, fn(data), title=f"{pid} {role} rev {rev}")
            rdocs.append({"role": role, "path": name, "revision": rev})
        manifest["revisions"] = [{"label": revision["label"], "documents": rdocs}]
        labels["revision"] = revision["expect"]
    S.write_json(d / "manifest.json", manifest)
    S.write_json(d / "labels.json", labels)


def field_labels(spec: dict, orig: dict, alt: dict, logistics: dict | None = None) -> dict[str, Any]:
    out = {"spec": S.truth_fields(spec), "original": S.truth_fields(orig), "alternate": S.truth_fields(alt)}
    return out


def main() -> None:
    # ---------------------------------------------------------------- dev-01 (the demo case)
    spec = dict(kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr=VENDOR_A, model="SYN-2500-A", rev="C", kva=2500, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye",
                dims=(2100, 1500, 2200), sections=[("core and coil", 3900)], total_kg=7600, heat_kw=14.8, lead_max=82, start="order")
    alt = dict(mfr=VENDOR_B, model="SPC-TX-2500", rev="A", kva=2500, pri_v=13800, sec_v=480, z_pct=5.0, family="delta-wye",
               dims=(2100, 1500, 2200), sections=[("core and coil", 4100)], total_kg=7800, lead_max=30, start="order")
    alt_b = {**alt, "rev": "B", "sections": [("core and coil, section 1", 2100), ("tank and fittings, section 2", 2050)]}
    log = dict(elevator_kg=3600, door=(2400, 2600), slab=3000, cooling_kw=20, ceiling=3000)
    sched = schedule_json(
        milestone={"name": "Energization", "install_test_weeks": 12}, order_release_week=0, submittal_approval_weeks=4,
        substituted_item="T1", substituted_item_label="transformer",
        items=[{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 82, "requires": True},
               {"id": "SWGR1", "name": "Main switchgear SWGR-1", "arrival_week": 80, "vendor": "Switchgear vendor", "requires": True}])
    labels = {
        "set": "dev",
        "fields": field_labels(spec, orig, alt),
        "findings": {"weight:elevator": "conclusive", "weight:slab": "cleared", "dims:door": "cleared", "dims:ceiling": "cleared",
                     "heat:cooling": "not_stated", "electrical:impedance": "needs_engineer"},
        "decision": {"answer": "no_not_alone", "baseline_week": 82, "max_recoverable_weeks": 2, "weeks_earlier_alternate_ships": 52,
                     "controlling_item_alternate": "Main switchgear SWGR-1", "requirements": [{"item": "Main switchgear SWGR-1", "must_be_ready_by_week": 78}]},
    }
    rev = {"label": "B", "docs": {"alternate": (T.tpl_b, alt_b, "alternate_revB.pdf", "B")},
           "expect": {"changed": {"weight:elevator": ["conclusive", "cleared"]}, "still_open": ["electrical:impedance", "heat:cooling"],
                      "milestone_moved": False, "answer_after": "no_not_alone"}}
    write_package("dev-01-oakridge", "Oakridge data hall: transformer T1 alternate (demo case)",
                  {"spec": (T.tpl_spec, spec, "spec.pdf"), "original": (T.tpl_a, orig, "original.pdf"), "alternate": (T.tpl_b, alt, "alternate.pdf")},
                  log, sched, 4, labels, rev)

    # ---------------------------------------------------------------- dev-02 (clean yes)
    spec = dict(kva=2000, pri_v=13800, sec_v=480, z_pct=5.75, vec="Dyn11", family="delta-wye", rev="A", tol=7.5)
    orig = dict(mfr=VENDOR_B, model="SPC-TX-2000", rev="B", kva=2000, pri_v=13800, sec_v=480, z_pct=5.75, family="delta-wye",
                dims=(2000, 1400, 2100), sections=[("core and coil", 3600)], total_kg=7000, noload_kw=2.9, load_kw=11.0, lead_max=82, start="order")
    alt = dict(mfr=VENDOR_C, model="IEW-2000-X", rev="A", kva=2000, pri_v=13800, sec_v=480, z_pct=5.75, family="delta-wye",
               dims=(1950, 1350, 2050), sections=[("core and coil", 3300)], total_kg=6700, heat_kw=11.5, lead_max=40, start="order")
    log = dict(elevator_kg=5000, door=(2400, 2600), slab=3000, cooling_kw=20, ceiling=3000)
    sched = schedule_json(
        milestone={"name": "Energization", "install_test_weeks": 10}, order_release_week=0, submittal_approval_weeks=4,
        substituted_item="T1", substituted_item_label="transformer",
        items=[{"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 82, "requires": True},
               {"id": "SWGR1", "name": "Main switchgear SWGR-1", "arrival_week": 60, "vendor": "Switchgear vendor", "requires": True}])
    orig_truth = S.truth_fields({**orig, "heat_kw": 13.9})
    labels = {
        "set": "dev",
        "fields": {"spec": S.truth_fields(spec), "original": orig_truth, "alternate": S.truth_fields(alt)},
        "findings": {"weight:elevator": "cleared", "weight:slab": "cleared", "dims:door": "cleared", "dims:ceiling": "cleared", "heat:cooling": "cleared"},
        "decision": {"answer": "yes", "baseline_week": 82, "max_recoverable_weeks": 22, "weeks_earlier_alternate_ships": 42,
                     "controlling_item_alternate": "Main switchgear SWGR-1", "requirements": []},
    }
    write_package("dev-02-birch", "Birch campus: transformer T1 alternate, same impedance",
                  {"spec": (T.tpl_spec, spec, "spec.pdf"), "original": (T.tpl_b, orig, "original.pdf"), "alternate": (T.tpl_c, alt, "alternate.pdf")},
                  log, sched, 12, labels)

    # ---------------------------------------------------------------- dev-03 (generator, heat conclusive)
    spec = dict(kva=2500, xd_pct=13.0, title="SECTION 26 32 13 - ENGINE GENERATOR SET", rev="A")
    orig = dict(mfr=VENDOR_A, model="SYN-GEN-2500", rev="B", kva=2500, xd_pct=12.0, dims=(6000, 2300, 2500), sections=[("generator set on skid", 17000)],
                total_kg=17000, heat_kw=165.0, lead_max=70, start="order", title="GENERATOR SET SUBMITTAL DATA SHEET")
    alt = dict(mfr=VENDOR_C, model="IEW-GEN-2500", rev="A", kva=2500, xd_pct=14.5, dims=(6200, 2300, 2600), sections=[("generator set on skid", 17500)],
               total_kg=17500, heat_kw=210.0, lead_max=36, start="approval")
    log = dict(door=(3200, 3400), slab=1500, cooling_kw=180, ceiling=4500)
    sched = schedule_json(
        milestone={"name": "Energization", "install_test_weeks": 12}, order_release_week=0, submittal_approval_weeks=6,
        substituted_item="G1", substituted_item_label="generator set",
        items=[{"id": "G1", "name": "Generator set G1", "baseline_arrival_week": 70, "requires": True},
               {"id": "PSWGR", "name": "Paralleling switchgear", "arrival_week": 66, "vendor": "Switchgear vendor", "requires": True}])
    labels = {
        "set": "dev",
        "fields": {"spec": S.truth_fields(spec), "original": S.truth_fields(orig), "alternate": S.truth_fields(alt)},
        "findings": {"weight:slab": "cleared", "dims:door": "cleared", "dims:ceiling": "cleared", "heat:cooling": "conclusive", "electrical:reactance": "needs_engineer"},
        "decision": {"answer": "no_not_alone", "baseline_week": 70, "max_recoverable_weeks": 4, "weeks_earlier_alternate_ships": 28,
                     "controlling_item_alternate": "Paralleling switchgear", "requirements": [{"item": "Paralleling switchgear", "must_be_ready_by_week": 64}]},
    }
    write_package("dev-03-cedar", "Cedar site: generator set G1 alternate",
                  {"spec": (T.tpl_spec, spec, "spec.pdf"), "original": (T.tpl_a, orig, "original.pdf"), "alternate": (T.tpl_a, alt, "alternate.pdf")},
                  log, sched, 6, labels)
    print("generated dev samples in", ROOT)


if __name__ == "__main__":
    main()
