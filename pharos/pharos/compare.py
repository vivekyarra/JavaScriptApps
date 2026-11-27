"""compare_substitution: what changed between spec, original equipment and the alternate."""
from __future__ import annotations

from typing import Any, Optional

from . import units as U
from .context import CaseContext
from .extract import FIELD_LABELS
from .schemas import CompareResult, Difference, FieldComparison, FieldValue, SupplierGap

COMMON_FIELDS = [
    "manufacturer",
    "model",
    "rated_kva",
    "primary_voltage_v",
    "secondary_voltage_v",
    "winding_config",
    "dimensions_mm",
    "heaviest_transport_weight_kg",
    "shipping_total_weight_kg",
    "total_weight_kg",
    "heat_loss_kw",
    "lead_time_weeks",
    "lead_time_start",
]
REQUIRED_FROM_SUPPLIER = {
    "rated_kva",
    "primary_voltage_v",
    "secondary_voltage_v",
    "winding_config",
    "dimensions_mm",
    "heaviest_transport_weight_kg",
    "total_weight_kg",
    "heat_loss_kw",
    "lead_time_weeks",
    "lead_time_start",
}
IDENTITY_FIELDS = {"manufacturer", "model"}
# capability fields: a spec value with no qualifier ("short-circuit rating 40 kA") is read as a minimum
CAPABILITY_FIELDS = {"continuous_current_a", "main_bus_a", "short_circuit_ka", "bil_kv"}
SWITCHGEAR_FIELDS = ["manufacturer", "model", "rated_voltage_kv", "continuous_current_a", "main_bus_a", "short_circuit_ka", "bil_kv",
                     "nema_type", "frequency_hz", "dimensions_mm", "heaviest_transport_weight_kg", "shipping_total_weight_kg",
                     "total_weight_kg", "lead_time_weeks", "lead_time_start"]
OPTIONAL_FIELDS = ["rated_voltage_kv", "continuous_current_a", "main_bus_a", "short_circuit_ka", "bil_kv", "nema_type", "frequency_hz"]


def applicable_fields(ctx: CaseContext) -> list[str]:
    if ctx.equipment_type == "switchgear":
        return list(SWITCHGEAR_FIELDS)
    extra = [
        f for f in OPTIONAL_FIELDS
        if any(ctx.fields.get(r, {}).get(f) and ctx.fields[r][f].status == "documented" for r in ("spec", "original", "alternate"))
    ]
    reactance = {
        "transformer": ["impedance_pct"],
        "generator": ["xd_subtransient_pct"],
    }.get(ctx.equipment_type)
    if reactance is None:
        found = [
            f
            for f in ("impedance_pct", "xd_subtransient_pct")
            if any(ctx.fields.get(r, {}).get(f) and ctx.fields[r][f].status == "documented" for r in ("spec", "original", "alternate"))
        ]
        reactance = found or ["impedance_pct"]
    fields = list(COMMON_FIELDS)
    idx = fields.index("winding_config")
    return fields[:idx] + reactance + fields[idx:-2] + extra + fields[-2:]


def _same(a: FieldValue, b: FieldValue) -> Optional[bool]:
    if a.status != "documented" or b.status != "documented":
        return None
    if a.field == "dimensions_mm":
        va = sorted(a.value["unordered"] if "unordered" in a.value else a.value.values())
        vb = sorted(b.value["unordered"] if "unordered" in b.value else b.value.values())
        return all(U.same_number(x, y, rel=5e-3) for x, y in zip(va, vb))
    if isinstance(a.value, (int, float)) and isinstance(b.value, (int, float)):
        return U.same_number(float(a.value), float(b.value), rel=1e-3)
    return str(a.value).strip().lower() == str(b.value).strip().lower()


def spec_deviation(spec: FieldValue, alt: FieldValue) -> Optional[bool]:
    """True when the alternate breaks a documented spec requirement; None when it cannot be judged."""
    if spec.status != "documented" or alt.status != "documented":
        return None
    if spec.field in IDENTITY_FIELDS or spec.field == "lead_time_start":
        return None
    if spec.field == "dimensions_mm":
        return None  # a spec rarely fixes overall dimensions; room limits are screened separately
    s, a = spec.value, alt.value
    if isinstance(s, (int, float)) and isinstance(a, (int, float)):
        if spec.qualifier == "min" or (spec.qualifier is None and spec.field in CAPABILITY_FIELDS):
            return a < s and not U.same_number(a, s, rel=1e-3)
        if spec.qualifier == "max":
            return a > s and not U.same_number(a, s, rel=1e-3)
        if spec.field == "impedance_pct":
            tol = (spec.detail or {}).get("tolerance_pct") if isinstance(spec.detail, dict) else None
            if tol is not None:
                return not (s * (1 - tol / 100.0) - 1e-9 <= a <= s * (1 + tol / 100.0) + 1e-9)
        return not U.same_number(a, s, rel=1e-3)
    return str(s).lower() != str(a).lower()


def _display(fv: FieldValue) -> Any:
    if fv.status != "documented":
        return None
    if fv.field == "dimensions_mm":
        v = fv.value
        return v if "unordered" not in v else {"unordered": v["unordered"]}
    return fv.value


def _gap_reason(fv: FieldValue, label: str) -> str:
    if fv.status == "could_not_read":
        return f"{label} was not found on readable pages; page(s) {fv.unreadable_pages} could not be read, so it may be there"
    if fv.status == "conflicting":
        return f"{label}: the submittal gives conflicting values"
    if any("ambiguous" in n for n in fv.notes):
        return f"{label}: a value was found but its unit is ambiguous"
    return f"the readable submittal does not state {label}"


def compare(ctx: CaseContext) -> CompareResult:
    if not ctx.has("alternate"):
        raise ValueError("compare_substitution needs an 'alternate' (supplier submittal) document")
    comps: list[FieldComparison] = []
    diffs: list[Difference] = []
    gaps: list[SupplierGap] = []
    for name in applicable_fields(ctx):
        spec, orig, alt = ctx.f("spec", name), ctx.f("original", name), ctx.f("alternate", name)
        changed = _same(orig, alt)
        changed_vs_orig = None if changed is None else (not changed)
        dev = spec_deviation(spec, alt)
        comps.append(
            FieldComparison(
                field=name,
                label=FIELD_LABELS.get(name, name),
                spec=spec,
                original=orig,
                alternate=alt,
                changed_vs_original=changed_vs_orig,
                deviates_from_spec=dev,
            )
        )
        if changed_vs_orig:
            diffs.append(
                Difference(
                    field=name,
                    label=FIELD_LABELS.get(name, name),
                    kind="changed_vs_original",
                    from_value=_display(orig),
                    to_value=_display(alt),
                    unit=alt.unit,
                    evidence=orig.evidence + alt.evidence,
                )
            )
        if dev:
            diffs.append(
                Difference(
                    field=name,
                    label=FIELD_LABELS.get(name, name),
                    kind="deviates_from_spec",
                    from_value=_display(spec),
                    to_value=_display(alt),
                    unit=alt.unit,
                    evidence=spec.evidence + alt.evidence,
                )
            )
        needed = (
            name in REQUIRED_FROM_SUPPLIER
            or name in {"impedance_pct", "xd_subtransient_pct"}
            or spec.status == "documented"
            or orig.status == "documented"
        )
        if needed and name not in IDENTITY_FIELDS and alt.status != "documented":
            gaps.append(
                SupplierGap(
                    field=name,
                    label=FIELD_LABELS.get(name, name),
                    status=alt.status,
                    reason=_gap_reason(alt, FIELD_LABELS.get(name, name)),
                    unreadable_pages=alt.unreadable_pages,
                )
            )
    n_doc = sum(1 for c in comps if c.alternate.status == "documented")
    summary = (
        f"{len(diffs)} documented difference(s) across {len(comps)} fields; "
        f"{n_doc} fields documented in the alternate submittal, {len(gaps)} not supplied or unreadable."
    )
    return CompareResult(
        case_id=ctx.case_id,
        equipment_type=ctx.equipment_type,
        documents=[d.ref() for d in ctx.docs.values()],
        fields=comps,
        differences=diffs,
        supplier_gaps=gaps,
        summary=summary,
    )


def _basis(spec: FieldValue) -> str:
    v, u = spec.value, spec.unit or ""
    val = f"{U.fmt(v) if isinstance(v, (int, float)) else v} {u}".strip()
    if spec.qualifier == "min":
        return f"at least {val}"
    if spec.qualifier == "max":
        return f"at most {val}"
    if spec.field in CAPABILITY_FIELDS:
        return f"at least {val} (an unqualified capability requirement is read as a minimum)"
    tol = (spec.detail or {}).get("tolerance_pct") if isinstance(spec.detail, dict) else None
    return f"{val}" + (f" within +/-{U.fmt(tol)} %" if tol is not None else " (exact)")


def _searched(doc, label: str) -> dict:
    return {
        "document": doc.name,
        "looking_for": label,
        "readable_pages": [p.number for p in doc.pages if p.status == "ok"],
        "unreadable_pages": [p.number for p in doc.pages if p.status != "ok"],
    }


def requirement_checks(fields: list[str], spec_f: dict, cand_f: dict, cand_doc) -> list:
    """Evaluate each buyer requirement against one candidate document. Shared by check_submittal and find_alternatives."""
    from .schemas import RequirementCheck

    def get(d: dict, name: str) -> FieldValue:
        return d.get(name) or FieldValue(field=name, status="not_stated", unit=None, confidence=0.0)

    reqs = []
    for name in fields:
        if name in IDENTITY_FIELDS or name == "lead_time_start":
            continue
        sp, al = get(spec_f, name), get(cand_f, name)
        label = FIELD_LABELS.get(name, name)
        if sp.status == "conflicting":
            reqs.append(RequirementCheck(field=name, label=label, basis="the specification states conflicting values", verdict="conflicting",
                                         requirement_evidence=sp.evidence, notes=["the buyer's own specification is ambiguous; resolve it first"]))
            continue
        if sp.status != "documented":
            continue
        base = dict(field=name, label=label, requirement=_display(sp), unit=sp.unit, basis=_basis(sp), requirement_evidence=sp.evidence)
        if al.status == "documented":
            dev = spec_deviation(sp, al)
            reqs.append(RequirementCheck(**base, submittal_value=_display(al), verdict="deviates" if dev else "complies",
                                         submittal_evidence=al.evidence, confidence=min(sp.confidence, al.confidence), notes=al.notes))
        elif al.status == "conflicting":
            reqs.append(RequirementCheck(**base, verdict="conflicting", submittal_evidence=al.evidence, notes=al.notes or ["the document states conflicting values"]))
        elif al.status == "could_not_read":
            reqs.append(RequirementCheck(**base, verdict="unreadable", submittal_evidence=al.evidence, searched=_searched(cand_doc, label), notes=al.notes))
        else:
            reqs.append(RequirementCheck(**base, verdict="missing", searched=_searched(cand_doc, label), notes=al.notes))
    return reqs


def check_submittal(ctx: CaseContext) -> "SubmittalCheck":
    from .schemas import SubmittalCheck

    if not ctx.has("alternate"):
        raise ValueError("check_submittal needs an 'alternate' (supplier submittal) document")
    if not ctx.has("spec"):
        raise ValueError("check_submittal needs a 'spec' (buyer specification) document")
    reqs = requirement_checks(applicable_fields(ctx), ctx.fields.get("spec", {}), ctx.fields.get("alternate", {}), ctx.docs["alternate"])
    counts = {v: sum(1 for r in reqs if r.verdict == v) for v in ("complies", "deviates", "missing", "unreadable", "conflicting")}
    warnings = sorted({n for role in ("spec", "original", "alternate") for fv in ctx.fields.get(role, {}).values() for n in fv.notes if "table lists" in n})
    return SubmittalCheck(
        case_id=ctx.case_id, equipment_type=ctx.equipment_type, offered_model=ctx.facts.get("offered_model"),
        documents=[d.ref() for d in ctx.docs.values() if d.role != "library"], requirements=reqs, counts=counts, table_warnings=warnings,
        summary=f"{len(reqs)} requirements: " + ", ".join(f"{n} {k}" for k, n in counts.items() if n) + ".",
    )
