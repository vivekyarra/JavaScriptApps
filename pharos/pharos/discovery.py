"""find_alternatives: candidate equivalents from a library the caller supplies, never from thin air.

Every candidate comes from a library document (a datasheet, or a row of a CSV catalogue) and is checked
against the buyer's requirements with the same logic as check_submittal, citing both sides. Nothing is
generated: an empty library, or one with no model that meets the requirements, returns none_supported.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Optional

from .compare import applicable_fields, requirement_checks
from .context import CaseContext
from .extract import _IEC_GROUP, _WORD_FAMILIES, FIELD_UNITS, _iec_family, extract_document, scan_identity
from .ingest import ParsedDocument
from .schemas import AlternativesResult, Candidate, Evidence, FieldValue
from .tables import find_row_tables, find_tables

CSV_NUMERIC = {
    "rated_kva", "primary_voltage_v", "secondary_voltage_v", "impedance_pct", "xd_subtransient_pct", "total_weight_kg",
    "heaviest_transport_weight_kg", "shipping_total_weight_kg", "heat_loss_kw", "lead_time_weeks", "rated_voltage_kv",
    "continuous_current_a", "main_bus_a", "short_circuit_ka", "bil_kv", "frequency_hz",
}
CSV_TEXT = {"manufacturer", "model", "winding_config", "nema_type"}


def _csv_candidates(doc: ParsedDocument) -> list[tuple[str, dict[str, FieldValue], str]]:
    text = doc.pages[0].text if doc.pages else ""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    header = [h.strip() for h in rows[0]]
    raw_lines = text.splitlines()
    out = []
    for i, row in enumerate(rows[1:], start=1):
        if not any(c.strip() for c in row):
            continue
        rec = dict(zip(header, row))
        line = raw_lines[i] if i < len(raw_lines) else ",".join(row)
        ev = Evidence(document=doc.name, role="library", revision=doc.effective_revision, sha256=doc.sha256, page=i, quote=line.strip(), verified=True)
        fields: dict[str, FieldValue] = {}
        for name in CSV_NUMERIC | CSV_TEXT:
            raw = (rec.get(name) or "").strip()
            if not raw:
                fields[name] = FieldValue(field=name, status="not_stated", unit=FIELD_UNITS.get(name), confidence=0.85, notes=["the catalogue row leaves this blank"])
            elif name in CSV_NUMERIC:
                try:
                    fields[name] = FieldValue(field=name, status="documented", value=float(raw.replace(",", "")), unit=FIELD_UNITS.get(name), evidence=[ev], confidence=0.9)
                except ValueError:
                    fields[name] = FieldValue(field=name, status="could_not_read", unit=FIELD_UNITS.get(name), evidence=[ev], notes=[f"'{raw}' is not a number"])
            else:
                val = raw
                if name == "winding_config":
                    g = _IEC_GROUP.search(raw)
                    val = (_iec_family(g.group(1)) if g else None) or next((fam for rx, fam in _WORD_FAMILIES if rx.search(raw)), raw)
                fields[name] = FieldValue(field=name, status="documented", value=val, evidence=[ev], confidence=0.9)
        out.append((f"row {i}", fields, rec.get("model", "").strip()))
    return out


def _doc_candidates(doc: ParsedDocument) -> list[tuple[str, dict[str, FieldValue], Optional[str]]]:
    """One candidate per model column of a multi-model table, else one for the whole datasheet."""
    models: list[tuple[int, list[str]]] = []
    for p in doc.pages:
        if p.status == "ok":
            for t in find_tables(p) + find_row_tables(p):
                models.append((t.page, t.models))
    out: list[tuple[str, dict[str, FieldValue], Optional[str]]] = []
    if models:
        page, names = models[0]
        for m in names:
            out.append((f"p.{page}, column '{m}'", extract_document(doc, m), m))
        return out
    _mans, mods = scan_identity(doc)
    values = {str(c.value) for c in mods}
    model = values.pop() if len(values) == 1 else None
    if not model:  # a datasheet title often carries the designation: 'DATASHEET - Maker IV-1000'
        head = " ".join(ln for p in doc.pages[:1] if p.status == "ok" for ln in p.text.splitlines()[:3])
        tok = _MODEL_TOKEN.findall(head)
        model = tok[0] if len(set(tok)) == 1 else None
    return [("whole document", extract_document(doc, None), model)]


_ORIG_LINE = re.compile(r"(?:original\s+model|basis\s+of\s+design|baseline\s+model|specified\s+model)[^:\n]*:\s*(?P<v>[^\n]+)", re.I)
_MODEL_TOKEN = re.compile(r"\b[A-Z]{1,6}-?\d{2,5}[A-Z]{0,3}(?:[-/][A-Z0-9]+)*\b")


def _norm_model(m: str) -> str:
    return re.sub(r"[^a-z0-9]", "", m.lower())


def _original_models(ctx: CaseContext) -> set[str]:
    """Models the buyer already has (named by the original document or by the specification), never offered back as alternatives."""
    out: set[str] = set()
    if ctx.has("original"):
        om = ctx.f("original", "model")
        if om.status == "documented":
            out.add(_norm_model(str(om.value)))
    spec = ctx.docs.get("spec")
    for p in (spec.pages if spec else []):
        for m in _ORIG_LINE.finditer(p.text if p.status == "ok" else ""):
            toks = _MODEL_TOKEN.findall(m.group("v"))
            out.update(_norm_model(t) for t in toks)
    return out


def find_alternatives(ctx: CaseContext, max_candidates: int = 10) -> AlternativesResult:
    if not ctx.has("spec"):
        raise ValueError("find_alternatives needs a 'spec' (buyer requirements) document")
    lib = [d for k, d in ctx.docs.items() if k.startswith("library:")]
    spec_f = ctx.fields.get("spec", {})
    fields = applicable_fields(ctx)
    originals = _original_models(ctx)
    used = [f for f in fields if spec_f.get(f) is not None and spec_f[f].status in {"documented", "conflicting"} and f not in {"manufacturer", "model", "lead_time_start"}]
    cands: list[Candidate] = []
    for doc in lib:
        entries = _csv_candidates(doc) if doc.kind == "csv" else _doc_candidates(doc)
        for ref, f, model in entries:
            if model and _norm_model(model) in originals:
                continue
            reqs = requirement_checks(fields, spec_f, f, doc)
            man = f.get("manufacturer")
            lt = f.get("lead_time_weeks")
            shortfalls = [f"{r.label}: {r.submittal_value} against {r.basis}" for r in reqs if r.verdict == "deviates"]
            open_pts = [f"{r.label}: {r.verdict}" for r in reqs if r.verdict in {"missing", "unreadable", "conflicting"}]
            notes: list[str] = []
            if not model:
                notes.append("the datasheet does not state a model designation; it cannot be ordered from this document alone")
            if any(re.search(r"\boption(al|s)?\b", p.text, re.I) for p in doc.pages if p.status == "ok"):
                notes.append("the document mentions options: confirm the exact configuration offered")
            verdict = "falls_short" if shortfalls else "needs_confirmation" if (open_pts or not model) else "supported"
            cands.append(Candidate(
                manufacturer=str(man.value) if man and man.status == "documented" else None, model=model or None, verdict=verdict,
                library_document=doc.name, library_ref=ref, requirements=reqs, matched=sum(1 for r in reqs if r.verdict == "complies"),
                shortfalls=shortfalls, open_points=open_pts, lead_time_weeks=float(lt.value) if lt and lt.status == "documented" else None, notes=notes,
            ))
    order = {"supported": 0, "needs_confirmation": 1, "falls_short": 2}
    cands.sort(key=lambda c: (order[c.verdict], -c.matched, len(c.shortfalls), c.manufacturer or "", c.model or ""))
    shown = cands[:max_candidates]
    ok = [c for c in cands if c.verdict != "falls_short"]
    mans = sorted({c.manufacturer for c in cands if c.manufacturer})
    n_s, n_c, n_f = (sum(1 for c in cands if c.verdict == v) for v in order)
    return AlternativesResult(
        case_id=ctx.case_id, equipment_type=ctx.equipment_type, requirements_used=used, library_documents=[d.name for d in lib],
        manufacturers_considered=mans, candidates=shown, none_supported=not ok,
        summary=(f"{len(cands)} model(s) found in {len(lib)} library document(s): {n_s} supported, {n_c} need confirmation, {n_f} fall short."
                 if lib else "No library was supplied, so no candidate can be proposed."),
    )
