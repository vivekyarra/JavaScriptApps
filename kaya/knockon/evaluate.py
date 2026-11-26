"""Evaluation harness: scores every layer against labels authored with the sample documents.

Layers: comparison (field extraction and read-status calls), screening (finding labels),
schedule and target (milestone answer), revision handling, and confidence calibration.
Sets: dev (used while building), milestone (two unfamiliar packages), final (run once).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from . import units as U
from .core import compare_substitution, decide_and_ask, load_manifest, screen_consequences
from .schemas import CaseInput, DocumentInput
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
RESULTS = ROOT / "eval" / "results"


def list_packages(set_name: str) -> list[Path]:
    sets = ["dev", "milestone", "final"] if set_name == "all" else [set_name]
    out: list[Path] = []
    for s in sets:
        d = SAMPLES / s
        if d.exists():
            out += sorted(p for p in d.iterdir() if (p / "manifest.json").exists())
    return out


def _value_match(expected: Any, got: Any) -> bool:
    if expected is None or got is None:
        return expected is None and got is None
    if isinstance(expected, list):
        if isinstance(got, dict):
            got = got.get("unordered") if "unordered" in got else sorted(got.values())
        got = sorted(got)
        return len(expected) == len(got) and all(U.same_number(float(a), float(b), rel=5e-3) for a, b in zip(sorted(expected), got))
    if isinstance(expected, (int, float)):
        return isinstance(got, (int, float)) and U.same_number(float(expected), float(got), rel=5e-3, abs_tol=0.05)
    return str(expected).lower() == str(got).lower()


def score_fields(cmp_res: Any, labels: dict[str, Any]) -> dict[str, Any]:
    by_role: dict[str, dict[str, Any]] = {}
    for comp in cmp_res.fields:
        by_role.setdefault("spec", {})[comp.field] = comp.spec
        by_role.setdefault("original", {})[comp.field] = comp.original
        by_role.setdefault("alternate", {})[comp.field] = comp.alternate
    total = correct = 0
    status_total = status_correct = 0
    misses: list[dict[str, Any]] = []
    calib: list[tuple[float, bool]] = []
    for role, fields in labels.get("fields", {}).items():
        for name, exp in fields.items():
            got = by_role.get(role, {}).get(name)
            if got is None:
                continue
            total += 1
            status_total += 1
            ok_status = got.status == exp["status"]
            status_correct += ok_status
            ok = ok_status
            if ok and exp["status"] == "documented":
                val = got.value
                if name == "dimensions_mm" and isinstance(val, dict):
                    val = val.get("unordered") if "unordered" in val else sorted(val.values())
                ok = _value_match(exp.get("value"), val)
            correct += ok
            if got.status == "documented":
                calib.append((got.confidence, bool(ok)))
            if not ok:
                misses.append({"role": role, "field": name, "expected": exp, "got": {"status": got.status, "value": got.value}})
    return {"total": total, "correct": correct, "status_total": status_total, "status_correct": status_correct, "misses": misses, "calib": calib}


def score_findings(scr: Any, labels: dict[str, Any]) -> dict[str, Any]:
    exp = labels.get("findings", {})
    got = {f.key: f.label for f in scr.findings}
    correct = sum(1 for k, v in exp.items() if got.get(k) == v)
    extra = sorted(k for k in got if k not in exp)
    wrong = [{"key": k, "expected": v, "got": got.get(k)} for k, v in exp.items() if got.get(k) != v]
    electrical_clearance = [f.key for f in scr.findings if f.topic == "electrical" and f.label in {"cleared", "conclusive"}]
    return {"expected": len(exp), "correct": correct, "false_positive_findings": extra, "wrong": wrong, "electrical_clearance_issued": electrical_clearance}


def score_decision(dec: Any, labels: dict[str, Any]) -> dict[str, Any]:
    exp = labels.get("decision", {})
    checks: dict[str, bool] = {}
    m = dec.milestone
    checks["answer"] = dec.answer == exp.get("answer")
    if "baseline_week" in exp:
        checks["baseline_week"] = bool(m) and U.same_number(m.baseline_week or -1, exp["baseline_week"], abs_tol=0.01)
    if "max_recoverable_weeks" in exp:
        checks["max_recoverable_weeks"] = bool(m) and m.max_recoverable_weeks is not None and U.same_number(m.max_recoverable_weeks, exp["max_recoverable_weeks"], abs_tol=0.01)
    if "weeks_earlier_alternate_ships" in exp:
        checks["weeks_earlier_alternate_ships"] = bool(m) and m.weeks_earlier_alternate_ships is not None and U.same_number(m.weeks_earlier_alternate_ships, exp["weeks_earlier_alternate_ships"], abs_tol=0.01)
    if "controlling_item_alternate" in exp:
        checks["controlling_item_alternate"] = bool(m) and m.controlling_item_alternate == exp["controlling_item_alternate"]
    if "requirements" in exp:
        got = {(r.item, round(r.must_be_ready_by_week, 2)) for r in dec.requirements_to_hit_target}
        want = {(r["item"], round(float(r["must_be_ready_by_week"]), 2)) for r in exp["requirements"]}
        checks["requirements"] = got == want
    return {"checks": checks, "passed": sum(checks.values()), "total": len(checks)}


def score_revision(dec2: Any, labels: dict[str, Any]) -> Optional[dict[str, Any]]:
    exp = labels.get("revision")
    if not exp:
        return None
    d = dec2.diff
    checks: dict[str, bool] = {}
    if d is None:
        return {"checks": {"diff_present": False}, "passed": 0, "total": 1}
    for key, (a, b) in exp.get("changed", {}).items():
        checks[f"changed:{key}"] = any(c["key"] == key and c["from"] == a and c["to"] == b for c in d.changed)
    for key in exp.get("still_open", []):
        checks[f"still_open:{key}"] = key in d.still_open
    for key in exp.get("removed", []):
        checks[f"removed:{key}"] = key in d.removed
    if "milestone_moved" in exp:
        checks["milestone_moved"] = d.milestone_moved == exp["milestone_moved"]
    if "answer_after" in exp:
        checks["answer_after"] = dec2.answer == exp["answer_after"]
    return {"checks": checks, "passed": sum(checks.values()), "total": len(checks)}


FROZEN_COMMIT = "b1a83d3"
FROZEN_FILES = ["knockon/extract.py", "knockon/units.py", "knockon/ingest.py", "knockon/screen.py", "knockon/compare.py", "knockon/decide.py", "knockon/context.py"]


def freeze_status() -> dict[str, Any]:
    """Prove the extraction and decision code is byte-identical to the frozen commit before the final run."""
    import hashlib
    import subprocess

    out: dict[str, Any] = {"frozen_commit": FROZEN_COMMIT, "files_unchanged": {}}
    try:
        for f in FROZEN_FILES:
            frozen = subprocess.run(["git", "show", f"{FROZEN_COMMIT}:{f}"], cwd=ROOT, capture_output=True, check=True).stdout
            current = (ROOT / f).read_bytes()
            out["files_unchanged"][f] = hashlib.sha256(frozen).hexdigest() == hashlib.sha256(current).hexdigest()
        out["all_unchanged"] = all(out["files_unchanged"].values())
        out["head"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception as exc:  # git unavailable: say so rather than claim a freeze
        out["all_unchanged"] = None
        out["error"] = str(exc)
    return out


def run_package(pkg: Path) -> dict[str, Any]:
    labels = json.loads((pkg / "labels.json").read_text(encoding="utf-8"))
    manifest, _ = load_manifest(str(pkg))
    store = Store(":memory:")
    inp = CaseInput(package_dir=str(pkg), case_id=f"eval-{pkg.name}")
    t0 = time.perf_counter()
    cmp_res = compare_substitution(inp, store)
    t1 = time.perf_counter()
    scr = screen_consequences(inp, store)
    t2 = time.perf_counter()
    dec = decide_and_ask(inp, store)
    t3 = time.perf_counter()
    out: dict[str, Any] = {
        "package": pkg.name,
        "set": labels.get("set"),
        "fields": score_fields(cmp_res, labels),
        "findings": score_findings(scr, labels),
        "decision": score_decision(dec, labels),
        "runtime_s": {"compare": round(t1 - t0, 3), "screen": round(t2 - t1, 3), "decide": round(t3 - t2, 3)},
        "answer": dec.answer,
        "headline": dec.headline,
    }
    revs = manifest.get("revisions") or []
    if revs and labels.get("revision"):
        rdocs = [DocumentInput(**d) for d in revs[0]["documents"]]
        t4 = time.perf_counter()
        dec2 = decide_and_ask(CaseInput(case_id=f"eval-{pkg.name}", package_dir=str(pkg), revised_documents=rdocs), store)
        out["revision_runtime_s"] = round(time.perf_counter() - t4, 3)
        out["revision"] = score_revision(dec2, labels)
        out["revision_headline"] = dec2.headline
    return out


def calibration_table(pairs: list[tuple[float, bool]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for conf, ok in pairs:
        b = "<0.6" if conf < 0.6 else "0.6-0.79" if conf < 0.8 else ">=0.8"
        buckets[b].append(ok)
    return [{"confidence": b, "n": len(v), "correct": sum(v), "accuracy": round(sum(v) / len(v), 3)} for b, v in sorted(buckets.items())]


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    def tot(path: str, key_c: str, key_t: str) -> tuple[int, int]:
        c = t = 0
        for r in results:
            x = r.get(path)
            if x:
                c += x[key_c]
                t += x[key_t]
        return c, t

    fc, ft = tot("fields", "correct", "total")
    sc, st = tot("fields", "status_correct", "status_total")
    fnc, fnt = tot("findings", "correct", "expected")
    dc, dt = tot("decision", "passed", "total")
    rc = rt = 0
    for r in results:
        if r.get("revision"):
            rc += r["revision"]["passed"]
            rt += r["revision"]["total"]
    fps = sum(len(r["findings"]["false_positive_findings"]) for r in results)
    clear = sum(len(r["findings"]["electrical_clearance_issued"]) for r in results)
    calib = [p for r in results for p in r["fields"]["calib"]]
    return {
        "packages": len(results),
        "fields_correct": f"{fc}/{ft}",
        "read_status_calls_correct": f"{sc}/{st}",
        "findings_correct": f"{fnc}/{fnt}",
        "false_positive_findings": fps,
        "electrical_clearances_issued": clear,
        "decision_checks_passed": f"{dc}/{dt}",
        "revision_checks_passed": f"{rc}/{rt}",
        "calibration": calibration_table(calib),
        "mean_runtime_s": round(sum(sum(r["runtime_s"].values()) for r in results) / max(len(results), 1), 3),
    }


def print_report(name: str, results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    print(f"\n=== {name}: {summary['packages']} package(s) ===")
    for r in results:
        f, fi, d = r["fields"], r["findings"], r["decision"]
        rev = r.get("revision")
        print(f"- {r['package']}: fields {f['correct']}/{f['total']}, findings {fi['correct']}/{fi['expected']} (+{len(fi['false_positive_findings'])} extra), "
              f"decision {d['passed']}/{d['total']}" + (f", revision {rev['passed']}/{rev['total']}" if rev else ""))
        for m in f["misses"][:12]:
            print(f"    field miss: {m['role']}.{m['field']} expected {m['expected']} got {m['got']}")
        for w in fi["wrong"]:
            print(f"    finding miss: {w}")
        if fi["false_positive_findings"]:
            print(f"    extra findings: {fi['false_positive_findings']}")
        for k, ok in d["checks"].items():
            if not ok:
                print(f"    decision check failed: {k}")
        if rev:
            for k, ok in rev["checks"].items():
                if not ok:
                    print(f"    revision check failed: {k}")
    print("summary:", json.dumps({k: v for k, v in summary.items() if k != "calibration"}))
    print("calibration (documented fields, confidence bucket vs correct):", summary["calibration"])


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="knockon-eval", description="Evaluate KNOCK-ON on the synthetic sample packages.")
    ap.add_argument("--set", default="dev", choices=["dev", "milestone", "final", "all"])
    ap.add_argument("--out", help="write full JSON results here")
    ap.add_argument("--rerun-final", action="store_true", help="allow re-running the final hold-out (this breaks the hold-out; disclose it)")
    args = ap.parse_args(argv)
    if args.set in {"final", "all"} and (RESULTS / "final.json").exists() and not args.rerun_final:
        print("The final hold-out has already been run once (eval/results/final.json). Re-running it would break the hold-out.\n"
              "Use --rerun-final only if you will disclose that.", file=sys.stderr)
        if args.set == "final":
            return 2
    pkgs = list_packages(args.set if (args.set != "all" or not (RESULTS / "final.json").exists() or args.rerun_final) else "all")
    if args.set == "all" and (RESULTS / "final.json").exists() and not args.rerun_final:
        pkgs = [p for p in pkgs if p.parent.name != "final"]
    if not pkgs:
        print(f"no packages found for set '{args.set}'", file=sys.stderr)
        return 1
    results = [run_package(p) for p in pkgs]
    summary = summarise(results)
    print_report(args.set, results, summary)
    payload = {"set": args.set, "summary": summary, "results": results}
    if args.set == "final":
        payload["freeze"] = freeze_status()
    for r in payload["results"]:
        r["fields"].pop("calib", None)
    target = args.out
    if args.set == "final" and not target:
        RESULTS.mkdir(parents=True, exist_ok=True)
        target = str(RESULTS / "final.json")
    if target:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
