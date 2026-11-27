"""Score Pharos on an independently authored blind set (blind/<scenario>/labels.json).

The scenarios were written by a separate author who never saw the code. The first run is written once to
eval/results/blind-first-run.json together with the git commit and a hash of every source file; a later run
refuses to overwrite it, so a re-run after fixes is a separate, labelled file and the first result stays public.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import core
from .schemas import CaseInput, DocumentInput
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
BLIND = ROOT / "blind"
RESULTS = ROOT / "eval" / "results"
LIB_PREFIXES = ("library", "lib", "datasheet", "catalog")


def source_fingerprint() -> dict[str, Any]:
    files = sorted((ROOT / "pharos").glob("*.py"))
    out: dict[str, Any] = {"files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16] for f in files}}
    try:
        out["commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        out["source_clean"] = subprocess.run(["git", "status", "--porcelain", "pharos"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() == ""
    except Exception:
        out["commit"], out["source_clean"] = None, None
    return out


def _docs(d: Path) -> list[DocumentInput]:
    docs = []
    for f in sorted(d.iterdir()):
        if f.name in {"labels.json", "manifest.json"} or f.suffix.lower() not in {".pdf", ".txt", ".csv"}:
            continue
        stem = f.stem.lower()
        role = "spec" if stem.startswith("spec") else "alternate" if stem.startswith(("alternate", "submittal")) else "original" if stem.startswith("original") else "library" if stem.startswith(LIB_PREFIXES) else None
        if role:
            docs.append(DocumentInput(role=role, path=str(f), name=f.name))
    return docs


def run_scenario(d: Path, lab: dict[str, Any]) -> dict[str, Any]:
    kind, exp = lab["kind"], lab["expected"]
    st = Store(":memory:")
    if kind == "check_submittal":
        res = core.check_submittal(CaseInput(documents=_docs(d), offered_model=lab.get("offered_model")), st)
        got = {r.field: r.verdict for r in res.requirements}
        want = exp["verdicts"]
        checks = {f: {"expected": v, "got": got.get(f), "ok": got.get(f) == v} for f, v in want.items()}
        extra = sorted(set(got) - set(want))
        return {"checks": checks, "unlabeled_fields_reported": extra}
    if kind == "decide":
        res = core.decide_and_ask(CaseInput(package_dir=str(d)), st)
        mx = res.milestone.max_recoverable_weeks if res.milestone else None
        want_mx = exp.get("max_recoverable_weeks")
        mx_ok = (mx is None and want_mx is None) or (mx is not None and want_mx is not None and abs(float(mx) - float(want_mx)) < 0.51)
        return {"checks": {"answer": {"expected": exp["answer"], "got": res.answer, "ok": res.answer == exp["answer"]},
                           "max_recoverable_weeks": {"expected": want_mx, "got": mx, "ok": mx_ok}}}
    if kind == "find_alternatives":
        res = core.find_alternatives(CaseInput(documents=_docs(d)), st)
        by: dict[str, set[str]] = {"supported": set(), "falls_short": set(), "needs_confirmation": set()}
        for c in res.candidates:
            by[c.verdict].add((c.model or "").strip())
        checks = {k: {"expected": sorted(exp.get(k, [])), "got": sorted(by[k]), "ok": set(exp.get(k, [])) == by[k]} for k in by}
        checks["none_supported"] = {"expected": exp.get("none_supported"), "got": res.none_supported, "ok": res.none_supported == exp.get("none_supported")}
        return {"checks": checks}
    raise ValueError(f"unknown kind {kind}")


def run(label: str) -> dict[str, Any]:
    scen = sorted(p for p in BLIND.iterdir() if (p / "labels.json").exists())
    rows, per_kind, per_pkg = [], {}, {}
    for d in scen:
        lab = json.loads((d / "labels.json").read_text(encoding="utf-8"))
        try:
            r = run_scenario(d, lab)
        except Exception as exc:  # a crash is a failure, recorded as such
            r = {"error": f"{type(exc).__name__}: {exc}", "checks": {}}
        ok = not r.get("error") and all(c["ok"] for c in r["checks"].values())
        n_ok = sum(c["ok"] for c in r["checks"].values())
        rows.append({"id": lab["id"], "package": lab["package"], "kind": lab["kind"], "scenario_ok": ok, "items_ok": n_ok, "items": len(r["checks"]), **r})
        for key, agg in ((lab["kind"], per_kind), (lab["package"], per_pkg)):
            a = agg.setdefault(key, {"scenarios": 0, "scenarios_ok": 0, "items": 0, "items_ok": 0})
            a["scenarios"] += 1
            a["scenarios_ok"] += ok
            a["items"] += len(r["checks"])
            a["items_ok"] += n_ok
    tot = {"scenarios": len(rows), "scenarios_ok": sum(r["scenario_ok"] for r in rows), "items": sum(r["items"] for r in rows), "items_ok": sum(r["items_ok"] for r in rows)}
    return {"label": label, "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fingerprint": source_fingerprint(), "totals": tot, "by_kind": per_kind, "by_package": per_pkg, "scenarios": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pharos-blind")
    ap.add_argument("--label", default="first-run", help="result file label; 'first-run' can be written once")
    args = ap.parse_args(argv)
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = "blind-first-run.json" if args.label == "first-run" else f"blind-{args.label}.json"
    out = RESULTS / name
    if out.exists():
        print(f"{out} already exists and is not overwritten; use --label <name> for a re-run", file=sys.stderr)
        return 2
    res = run(args.label)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    t = res["totals"]
    print(f"{t['scenarios_ok']}/{t['scenarios']} scenarios fully correct; {t['items_ok']}/{t['items']} labelled items correct -> {out}")
    for r in res["scenarios"]:
        if not r["scenario_ok"]:
            bad = [f"{k}: expected {c['expected']} got {c['got']}" for k, c in r["checks"].items() if not c["ok"]]
            print(f"  FAIL {r['id']} ({r['kind']}): {r.get('error') or '; '.join(bad)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
