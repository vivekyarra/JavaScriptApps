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


def applicable_fields(ctx: CaseContext) -> list[str]:
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
    return fields[:idx] + reactance + fields[idx:]


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
        if spec.qualifier == "min":
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
