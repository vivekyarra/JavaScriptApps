"""Shared core: the three tools, used identically by the MCP server, the API and the UI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from .compare import check_submittal as _check_submittal
from .compare import compare as _compare
from .context import CaseContext, build_context
from .decide import decide as _decide
from .discovery import find_alternatives as _find_alternatives
from .ingest import ParsedDocument, load_document
from .schemas import (
    CaseInput,
    CompareResult,
    DecisionDiff,
    DecisionResult,
    DocumentInput,
    ScreenResult,
)
from .screen import screen as _screen
from .store import Store

_DEFAULT_STORE: Optional[Store] = None


def get_store(store: Optional[Store] = None) -> Store:
    global _DEFAULT_STORE
    if store is not None:
        return store
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = Store()
    return _DEFAULT_STORE


def set_default_store(store: Optional[Store]) -> None:
    global _DEFAULT_STORE
    _DEFAULT_STORE = store


def load_manifest(package_dir: str) -> tuple[dict[str, Any], Path]:
    base = Path(package_dir)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    return manifest, base


def _docs_from_inputs(inputs: list[DocumentInput], base: Optional[Path]) -> list[ParsedDocument]:
    return [load_document(d, base) for d in inputs]


def _auto_case_id(docs: list[ParsedDocument]) -> str:
    h = hashlib.sha256("".join(sorted(f"{d.role}:{d.sha256}" for d in docs)).encode()).hexdigest()
    return f"case-{h[:10]}"


def prepare_case(inp: CaseInput, store: Store) -> CaseContext:
    """Resolve inputs into a CaseContext, persisting immutable document revisions."""
    base: Optional[Path] = None
    docs_in = list(inp.documents)
    facts = dict(inp.project_facts or {})
    if inp.offered_model:
        facts["offered_model"] = inp.offered_model
    if inp.equipment_type:
        facts["equipment_type"] = inp.equipment_type
    target = inp.recovery_target_weeks
    title: Optional[str] = None
    if inp.package_dir:
        manifest, base = load_manifest(inp.package_dir)
        title = manifest.get("title")
        if not docs_in:
            docs_in = [DocumentInput(**d) for d in manifest.get("documents", [])]
        if target is None and isinstance(manifest.get("recovery_target_weeks"), (int, float)):
            target = float(manifest["recovery_target_weeks"])
        if isinstance(manifest.get("project_facts"), dict):
            facts = {**manifest["project_facts"], **facts}
    if target is not None and target < 0:
        raise ValueError("recovery_target_weeks must not be negative")
    if inp.library_dir:
        lib = Path(inp.library_dir)
        for f in sorted(lib.rglob("*")):
            if f.is_file() and f.suffix.lower() in {".pdf", ".txt", ".csv"}:
                docs_in.append(DocumentInput(role="library", path=str(f), name=str(f.relative_to(lib))))
    loaded = _docs_from_inputs(docs_in, base)
    revised = _docs_from_inputs(list(inp.revised_documents), base)

    case_id = inp.case_id
    if case_id is None:
        if not loaded:
            raise ValueError("provide case_id, package_dir or documents")
        case_id = _auto_case_id(loaded)
    store.ensure_case(case_id, title)
    for d in loaded + revised:
        store.add_document(case_id, d)
    active = store.active_documents(case_id)
    if not active:
        raise ValueError(f"case '{case_id}' has no documents; provide documents or package_dir")
    saved_facts, saved_target = store.case_inputs(case_id)
    merged_facts = {**saved_facts, **facts}
    eff_target = target if target is not None else saved_target
    store.set_case_inputs(case_id, facts or None, target)
    return build_context(case_id, active, merged_facts, eff_target)


def check_submittal(inp: CaseInput, store: Optional[Store] = None):
    st = get_store(store)
    return _check_submittal(prepare_case(inp, st))


def find_alternatives(inp: CaseInput, store: Optional[Store] = None, max_candidates: int = 10):
    st = get_store(store)
    return _find_alternatives(prepare_case(inp, st), max_candidates)


def compare_substitution(inp: CaseInput, store: Optional[Store] = None) -> CompareResult:
    st = get_store(store)
    return _compare(prepare_case(inp, st))


def screen_consequences(inp: CaseInput, store: Optional[Store] = None) -> ScreenResult:
    st = get_store(store)
    return _screen(prepare_case(inp, st))


def _signature(f: dict[str, Any]) -> str:
    """What a finding rests on: its computed values and quoted evidence (not the revision letter in its prose)."""
    quotes = sorted(e["quote"] for e in (f.get("supplier_evidence") or []) + (f.get("requirement_evidence") or []))
    return json.dumps({"computed": f.get("computed") or {}, "quotes": quotes}, sort_keys=True, default=str)


def _diff(prev: dict[str, Any], new: DecisionResult) -> DecisionDiff:
    pf = {f["key"]: f for f in prev.get("findings", [])}
    nf = {f.key: f for f in new.findings}
    changed, updated, still_open, unchanged_settled = [], [], [], []
    for key, f in nf.items():
        if key in pf:
            before = pf[key]["label"]
            if before != f.label:
                changed.append({"key": key, "title": f.title, "from": before, "to": f.label})
            elif _signature(pf[key]) != _signature(f.model_dump(mode="json")):
                updated.append({"key": key, "title": f.title, "label": f.label, "note": "same label, details changed"})
            elif f.label in {"conclusive", "cleared"}:
                unchanged_settled.append(key)
            else:
                still_open.append(key)
    pm, nm = prev.get("milestone") or {}, new.milestone
    mp = pm.get("max_recoverable_weeks")
    mn = nm.max_recoverable_weeks if nm else None
    moved = bool(nm) and (
        mp != mn or pm.get("baseline_week") != nm.baseline_week or pm.get("alternate_week_best") != nm.alternate_week_best
    ) or (not nm and bool(pm))
    return DecisionDiff(
        from_version=prev["version"],
        to_version=new.version,
        changed=changed,
        updated=updated,
        still_open=still_open,
        unchanged_settled=unchanged_settled,
        new=[k for k in nf if k not in pf],
        removed=[k for k in pf if k not in nf],
        milestone_moved=moved,
        answer_before=prev.get("answer"),
        answer_after=new.answer,
        max_recoverable_before=mp,
        max_recoverable_after=mn,
    )


def decide_and_ask(inp: CaseInput, store: Optional[Store] = None) -> DecisionResult:
    st = get_store(store)
    ctx = prepare_case(inp, st)
    prev_hash = st.latest_hash(ctx.case_id)
    if prev_hash == ctx.inputs_hash:
        latest = st.latest_decision(ctx.case_id)
        if latest is not None:
            res = DecisionResult.model_validate(latest)
            res.history = st.history(ctx.case_id)
            return res
    cmp_res = _compare(ctx)
    scr = _screen(ctx)
    res = _decide(ctx, scr, cmp_res)
    res.version = st.next_version(ctx.case_id)
    prev = st.latest_decision(ctx.case_id)
    if prev is not None:
        res.diff = _diff(prev, res)
    st.save_decision(
        ctx.case_id, res.version, ctx.inputs_hash, res.answer,
        res.milestone.max_recoverable_weeks if res.milestone else None, json.loads(res.model_dump_json(exclude={"history"})),
    )
    res.history = st.history(ctx.case_id)
    return res
