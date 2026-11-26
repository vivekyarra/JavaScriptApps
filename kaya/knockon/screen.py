"""screen_consequences: link each documented change to a specific project constraint.

Labels: conclusive / cleared (one constraint only) / needs_engineer / not_stated / could_not_read.
No electrical clearance is issued: an impedance change always returns "engineer review needed".
"""
from __future__ import annotations

from typing import Any, Optional

from . import units as U
from .compare import applicable_fields, spec_deviation
from .context import CaseContext
from .extract import FIELD_LABELS
from .schemas import Evidence, Finding, FollowUp, FieldValue, ScreenResult


def _lc(text: str) -> str:
    """Lower-case only the first letter so '(%Z)' and 'kVA' keep their case."""
    return text[:1].lower() + text[1:]


def _unit_name(ctx: CaseContext) -> str:
    model = ctx.f("alternate", "model")
    if model.status == "documented":
        return f"the alternate ({model.value})"
    return "the alternate unit"


def _min_conf(*fvs: FieldValue) -> float:
    vals = [fv.confidence for fv in fvs if fv.status == "documented"]
    return round(min(vals), 2) if vals else 0.0


def _page_ref(ev: list[Evidence]) -> str:
    if not ev:
        return "the submittal"
    e = ev[0]
    rev = f", rev {e.revision}" if e.revision else ""
    return f"{e.document} p.{e.page}{rev}"


def _gap_finding(ctx: CaseContext, key: str, topic: str, fv: FieldValue, what: str, ask: str) -> Finding:
    if fv.status == "could_not_read":
        pages = fv.unreadable_pages
        doc = next((e.document for e in fv.evidence), None) or ctx.docs["alternate"].name
        return Finding(
            key=key,
            topic=topic,  # type: ignore[arg-type]
            label="could_not_read",
            title=f"{what}: could not read",
            summary=f"{what} was not found on the readable pages, and page(s) {pages} of the submittal could not be read, so it may be stated there.",
            supplier_evidence=fv.evidence,
            follow_up=FollowUp(
                kind="readable_copy",
                question=f"Page(s) {pages} of {doc} could not be read (scanned or image-only). Please send a text-based copy so {_lc(what)} can be checked, or confirm it by hand.",
            ),
            confidence=0.0,
        )
    if fv.status == "conflicting":
        cands = (fv.detail or {}).get("candidates", [])
        txt = "; ".join(f"{c.get('value')} (p.{c.get('page')})" for c in cands)
        return Finding(
            key=key,
            topic=topic,  # type: ignore[arg-type]
            label="not_stated",
            title=f"{what}: conflicting values",
            summary=f"The submittal gives conflicting values for {_lc(what)}: {txt}. Treated as not reliably stated.",
            supplier_evidence=fv.evidence,
            follow_up=FollowUp(kind="vendor", question=f"The submittal gives conflicting values for {_lc(what)} ({txt}). Please confirm the correct value and reissue the page."),
            confidence=0.0,
        )
    ambiguous = any("ambiguous" in n for n in fv.notes)
    return Finding(
        key=key,
        topic=topic,  # type: ignore[arg-type]
        label="not_stated",
        title=f"{what}: not stated",
        summary=(f"A weight in 'ton(s)' was found but its unit is ambiguous; {_lc(what)} is treated as not stated." if ambiguous
                 else f"The readable submittal does not state {_lc(what)}."),
        supplier_evidence=fv.evidence,
        follow_up=FollowUp(kind="vendor", question=ask),
        confidence=fv.confidence,
    )


def _constraint_dict(name: str, fv: FieldValue) -> dict[str, Any]:
    return {"name": FIELD_LABELS.get(name, name), "field": name, "value": fv.value, "unit": fv.unit}


# ----------------------------------------------------------------------- physical
def _elevator(ctx: CaseContext, missing: list[str]) -> Optional[Finding]:
    cap = ctx.constraints["elevator_capacity_kg"]
    if cap.status != "documented":
        if cap.status == "conflicting":
            missing.append("freight elevator capacity (the logistics document and project facts disagree)")
        else:
            missing.append("freight elevator capacity (needed to check the heaviest transported section)")
        return None
    hv = ctx.f("alternate", "heaviest_transport_weight_kg")
    ship_total = ctx.f("alternate", "shipping_total_weight_kg")
    total = ctx.f("alternate", "total_weight_kg")
    cap_kg = float(cap.value)
    cdict = _constraint_dict("elevator_capacity_kg", cap)
    scope = "Clears this one constraint only: the route, turns and installation are checked separately."
    if hv.status == "documented":
        w = float(hv.value)
        conf = _min_conf(hv, cap)
        if w > cap_kg:
            return Finding(
                key="weight:elevator", topic="physical", label="conclusive",
                title="Heaviest shipping section exceeds the freight elevator limit",
                summary=f"The heaviest shipping section is {U.fmt(w)} kg ({_page_ref(hv.evidence)}); the freight elevator is limited to {U.fmt(cap_kg)} kg. The elevator route fails for that section.",
                constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=hv.evidence,
                formula=f"{U.fmt(w)} kg > {U.fmt(cap_kg)} kg", computed={"transported_kg": w, "limit_kg": cap_kg, "excess_kg": round(w - cap_kg, 1)},
                follow_up=FollowUp(kind="route", question=f"The heaviest shipping section is {U.fmt(w)} kg but the freight elevator limit is {U.fmt(cap_kg)} kg. Can the unit ship in sections no heavier than {U.fmt(cap_kg)} kg, or is another documented route available?"),
                confidence=conf,
            )
        return Finding(
            key="weight:elevator", topic="physical", label="cleared",
            title="Heaviest shipping section is within the freight elevator limit",
            summary=f"The heaviest shipping section is {U.fmt(w)} kg ({_page_ref(hv.evidence)}); the freight elevator limit is {U.fmt(cap_kg)} kg.",
            constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=hv.evidence,
            formula=f"{U.fmt(w)} kg ≤ {U.fmt(cap_kg)} kg", computed={"transported_kg": w, "limit_kg": cap_kg, "margin_kg": round(cap_kg - w, 1)},
            scope_note=scope, confidence=conf,
        )
    bound = ship_total if ship_total.status == "documented" else total if total.status == "documented" else None
    if hv.status in {"not_stated", "could_not_read", "conflicting"} and bound is not None:
        t = float(bound.value)
        if t <= cap_kg:
            return Finding(
                key="weight:elevator", topic="physical", label="cleared",
                title="Total weight is within the freight elevator limit, so every section is",
                summary=f"The submittal gives no shipping split, but the total is {U.fmt(t)} kg ({_page_ref(bound.evidence)}), at or below the {U.fmt(cap_kg)} kg elevator limit, so no section can exceed it.",
                constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=bound.evidence,
                formula=f"{U.fmt(t)} kg ≤ {U.fmt(cap_kg)} kg", computed={"bounding_total_kg": t, "limit_kg": cap_kg},
                scope_note=scope + " Bounded by the stated total weight, not by a stated shipping split.",
                confidence=min(_min_conf(bound, cap), 0.8),
            )
        return Finding(
            key="weight:elevator", topic="physical", label="not_stated",
            title="Shipping split not stated; total weight exceeds the elevator limit",
            summary=f"The submittal states a total of {U.fmt(t)} kg ({_page_ref(bound.evidence)}) but no shipping sections. If it ships whole it exceeds the {U.fmt(cap_kg)} kg elevator limit; if it ships in lighter sections it may not.",
            constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=bound.evidence,
            computed={"total_kg": t, "limit_kg": cap_kg},
            follow_up=FollowUp(kind="vendor", question=f"Please state the shipping sections and the weight of each. The freight elevator limit is {U.fmt(cap_kg)} kg and the stated total is {U.fmt(t)} kg."),
            confidence=bound.confidence,
        )
    return _gap_finding(
        ctx, "weight:elevator", "physical", hv, "Heaviest shipping section",
        f"Please state the shipping sections and the weight of each. The freight elevator limit is {U.fmt(cap_kg)} kg.",
    )


def _footprint_bounds(dims: FieldValue) -> Optional[tuple[float, float, bool]]:
    """(min_area_m2, max_area_m2, ordered)."""
    v = dims.value
    if dims.status != "documented":
        return None
    if "unordered" in v:
        d = sorted(v["unordered"])
        return (d[0] * d[1] / 1e6, d[1] * d[2] / 1e6, False)
    a = v["length"] * v["width"] / 1e6
    return (a, a, True)


def _slab(ctx: CaseContext, missing: list[str]) -> Optional[Finding]:
    lim = ctx.constraints["slab_limit_kg_m2"]
    if lim.status != "documented":
        missing.append("floor loading limit (needed to check weight per area)")
        return None
    total = ctx.f("alternate", "total_weight_kg")
    dims = ctx.f("alternate", "dimensions_mm")
    cdict = _constraint_dict("slab_limit_kg_m2", lim)
    if total.status != "documented":
        return _gap_finding(ctx, "weight:slab", "physical", total, "Total weight",
                            f"Please state the total in-service weight (including oil/coolant) so it can be checked against the {U.fmt(float(lim.value))} kg/m² floor limit.")
    fb = _footprint_bounds(dims)
    if fb is None:
        return _gap_finding(ctx, "weight:slab", "physical", dims, "Overall dimensions",
                            "Please state the overall length and width (footprint) so floor loading can be checked.")
    w, limit = float(total.value), float(lim.value)
    lo_area, hi_area, ordered = fb
    p_hi = w / lo_area  # highest possible average pressure
    p_lo = w / hi_area
    conf = _min_conf(total, dims, lim)
    ev = total.evidence + dims.evidence
    if p_lo > limit:
        return Finding(
            key="weight:slab", topic="physical", label="conclusive",
            title="Average floor pressure exceeds the floor loading limit",
            summary=f"{U.fmt(w)} kg over the stated footprint gives about {U.fmt(p_lo, 0)} kg/m², above the {U.fmt(limit)} kg/m² limit. Concentrated loads under skids would be higher still.",
            constraint=cdict, requirement_evidence=lim.evidence, supplier_evidence=ev,
            formula=f"{U.fmt(w)} kg / {U.fmt(hi_area, 2)} m² = {U.fmt(p_lo, 0)} kg/m² > {U.fmt(limit)} kg/m²",
            computed={"pressure_kg_m2": round(p_lo, 1), "limit_kg_m2": limit},
            follow_up=FollowUp(kind="vendor", question=f"The unit's average floor pressure is about {U.fmt(p_lo, 0)} kg/m² against a {U.fmt(limit)} kg/m² limit. Please confirm whether a spreader frame or alternative support is documented."),
            confidence=conf,
        )
    if p_hi <= limit:
        return Finding(
            key="weight:slab", topic="physical", label="cleared",
            title="Average floor pressure is within the floor loading limit",
            summary=f"{U.fmt(w)} kg over the stated footprint is at most about {U.fmt(p_hi, 0)} kg/m², within the {U.fmt(limit)} kg/m² limit.",
            constraint=cdict, requirement_evidence=lim.evidence, supplier_evidence=ev,
            formula=f"{U.fmt(w)} kg / {U.fmt(lo_area, 2)} m² = {U.fmt(p_hi, 0)} kg/m² ≤ {U.fmt(limit)} kg/m²",
            computed={"pressure_kg_m2": round(p_hi, 1), "limit_kg_m2": limit},
            scope_note="Clears the average floor pressure only. Concentrated loads under skids or rails are not assessed.",
            confidence=conf,
        )
    return Finding(
        key="weight:slab", topic="physical", label="not_stated",
        title="Dimension order not labelled; floor pressure cannot be concluded",
        summary="The overall dimensions are not labelled length / width / height, and the floor result depends on which two form the footprint.",
        constraint=cdict, requirement_evidence=lim.evidence, supplier_evidence=ev,
        follow_up=FollowUp(kind="vendor", question="Please label the overall dimensions as length, width and height (or give the footprint) so floor loading can be checked."),
        confidence=conf,
    )


def _door(ctx: CaseContext, missing: list[str]) -> Optional[Finding]:
    dw, dh = ctx.constraints["door_width_mm"], ctx.constraints["door_height_mm"]
    if dw.status != "documented" or dh.status != "documented":
        missing.append("door clear width and height (needed to check overall dimensions)")
        return None
    dims = ctx.f("alternate", "dimensions_mm")
    cdict = {"name": "Door opening (width × height)", "field": "door_width_mm/door_height_mm", "value": [dw.value, dh.value], "unit": "mm"}
    if dims.status != "documented":
        return _gap_finding(ctx, "dims:door", "physical", dims, "Overall dimensions",
                            f"Please state the overall length, width and height. The delivery door opening is {U.fmt(float(dw.value))} × {U.fmt(float(dh.value))} mm.")
    W, H = float(dw.value), float(dh.value)
    v = dims.value
    conf = _min_conf(dims, dw, dh)
    ev = dw.evidence + dh.evidence
    if "unordered" in v:
        a, b, c = sorted(v["unordered"])
        fits_any = (a <= min(W, H)) and (b <= max(W, H))
        if not fits_any:
            return Finding(
                key="dims:door", topic="physical", label="conclusive",
                title="Overall dimensions cannot pass the door opening in any orientation",
                summary=f"The two smallest dimensions are {U.fmt(a)} × {U.fmt(b)} mm; the door opening is {U.fmt(W)} × {U.fmt(H)} mm.",
                constraint=cdict, requirement_evidence=ev, supplier_evidence=dims.evidence,
                formula=f"{U.fmt(a)} × {U.fmt(b)} mm does not fit {U.fmt(W)} × {U.fmt(H)} mm",
                computed={"smallest_cross_section_mm": [a, b], "door_mm": [W, H]},
                follow_up=FollowUp(kind="vendor", question=f"The unit's smallest cross-section is {U.fmt(a)} × {U.fmt(b)} mm against a {U.fmt(W)} × {U.fmt(H)} mm door. Can it ship in sections that pass?"),
                confidence=conf,
            )
        return Finding(
            key="dims:door", topic="physical", label="cleared",
            title="Overall dimensions can pass the door opening",
            summary=f"Its two smallest dimensions ({U.fmt(a)} × {U.fmt(b)} mm) fit the {U.fmt(W)} × {U.fmt(H)} mm door opening in some orientation.",
            constraint=cdict, requirement_evidence=ev, supplier_evidence=dims.evidence,
            computed={"smallest_cross_section_mm": [a, b], "door_mm": [W, H]},
            scope_note="Clears this door only, and only if the unit may be moved in the orientation that fits (dimension order is not labelled). Turns, corridors and installation are not assessed.",
            confidence=min(conf, 0.7),
        )
    cw, ch = min(v["length"], v["width"]), v["height"]
    if cw <= W and ch <= H:
        return Finding(
            key="dims:door", topic="physical", label="cleared",
            title="Overall dimensions pass the door opening upright",
            summary=f"Upright cross-section {U.fmt(cw)} × {U.fmt(ch)} mm fits the {U.fmt(W)} × {U.fmt(H)} mm door opening.",
            constraint=cdict, requirement_evidence=ev, supplier_evidence=dims.evidence,
            formula=f"{U.fmt(cw)} ≤ {U.fmt(W)} and {U.fmt(ch)} ≤ {U.fmt(H)}", computed={"cross_section_mm": [cw, ch], "door_mm": [W, H]},
            scope_note="Clears this door only. Turns, corridors and installation are not assessed.", confidence=conf,
        )
    tilt_ok = sorted([v["length"], v["width"], v["height"]])
    could_tilt = tilt_ok[0] <= min(W, H) and tilt_ok[1] <= max(W, H)
    extra = " It would pass only if laid on its side, which the submittal does not state is permitted." if could_tilt else ""
    return Finding(
        key="dims:door", topic="physical", label="conclusive",
        title="Overall dimensions do not pass the door opening upright",
        summary=f"Upright cross-section {U.fmt(cw)} × {U.fmt(ch)} mm does not fit the {U.fmt(W)} × {U.fmt(H)} mm door opening.{extra}",
        constraint=cdict, requirement_evidence=ev, supplier_evidence=dims.evidence,
        formula=f"{U.fmt(cw)} × {U.fmt(ch)} mm vs {U.fmt(W)} × {U.fmt(H)} mm", computed={"cross_section_mm": [cw, ch], "door_mm": [W, H], "passes_if_tilted": could_tilt},
        follow_up=FollowUp(kind="vendor", question=f"The unit's upright cross-section is {U.fmt(cw)} × {U.fmt(ch)} mm against a {U.fmt(W)} × {U.fmt(H)} mm door. Can it be tilted or shipped in sections that pass?"),
        confidence=conf,
    )


def _ceiling(ctx: CaseContext, missing: list[str]) -> Optional[Finding]:
    cl = ctx.constraints["ceiling_clearance_mm"]
    if cl.status != "documented":
        return None  # optional constraint: not listed as missing unless a document discusses it
    dims = ctx.f("alternate", "dimensions_mm")
    cdict = _constraint_dict("ceiling_clearance_mm", cl)
    if dims.status != "documented":
        return _gap_finding(ctx, "dims:ceiling", "physical", dims, "Overall dimensions",
                            f"Please state the overall height. The room's overhead clearance is {U.fmt(float(cl.value))} mm.")
    v = dims.value
    limit = float(cl.value)
    conf = _min_conf(dims, cl)
    if "unordered" in v:
        mx = max(v["unordered"])
        if mx <= limit:
            return Finding(key="dims:ceiling", topic="physical", label="cleared", title="Largest dimension is within the overhead clearance",
                           summary=f"Even the largest dimension ({U.fmt(mx)} mm) is within the {U.fmt(limit)} mm overhead clearance.",
                           constraint=cdict, requirement_evidence=cl.evidence, supplier_evidence=dims.evidence,
                           scope_note="Clears overhead clearance only.", confidence=conf)
        return Finding(key="dims:ceiling", topic="physical", label="not_stated", title="Height not labelled; overhead clearance cannot be concluded",
                       summary="The dimensions are not labelled, and the largest dimension exceeds the overhead clearance.",
                       constraint=cdict, requirement_evidence=cl.evidence, supplier_evidence=dims.evidence,
                       follow_up=FollowUp(kind="vendor", question="Please label the overall dimensions (length, width, height)."), confidence=conf)
    h = float(v["height"])
    if h > limit:
        return Finding(key="dims:ceiling", topic="physical", label="conclusive", title="Unit height exceeds the overhead clearance",
                       summary=f"Unit height {U.fmt(h)} mm exceeds the {U.fmt(limit)} mm overhead clearance.",
                       constraint=cdict, requirement_evidence=cl.evidence, supplier_evidence=dims.evidence,
                       formula=f"{U.fmt(h)} mm > {U.fmt(limit)} mm", computed={"height_mm": h, "limit_mm": limit},
                       follow_up=FollowUp(kind="vendor", question=f"The unit is {U.fmt(h)} mm tall against {U.fmt(limit)} mm overhead clearance. Can the height be reduced or the unit shipped differently?"),
                       confidence=conf)
    return Finding(key="dims:ceiling", topic="physical", label="cleared", title="Unit height is within the overhead clearance",
                   summary=f"Unit height {U.fmt(h)} mm is within the {U.fmt(limit)} mm overhead clearance.",
                   constraint=cdict, requirement_evidence=cl.evidence, supplier_evidence=dims.evidence,
                   formula=f"{U.fmt(h)} mm ≤ {U.fmt(limit)} mm", scope_note="Clears overhead clearance only.", confidence=conf)


def _heat(ctx: CaseContext, missing: list[str]) -> Optional[Finding]:
    cap = ctx.constraints["cooling_capacity_kw"]
    heat = ctx.f("alternate", "heat_loss_kw")
    if cap.status != "documented":
        if heat.status == "documented":
            missing.append("room cooling capacity (needed to check the alternate's heat loss)")
        return None
    cdict = _constraint_dict("cooling_capacity_kw", cap)
    if heat.status != "documented":
        return _gap_finding(ctx, "heat:cooling", "physical", heat, "Heat loss",
                            f"Please state the total heat loss / heat rejection at rated load. The documented cooling allowance is {U.fmt(float(cap.value))} kW.")
    h, c = float(heat.value), float(cap.value)
    conf = _min_conf(heat, cap)
    if h > c:
        return Finding(key="heat:cooling", topic="physical", label="conclusive", title="Heat loss exceeds the documented cooling allowance",
                       summary=f"The alternate's heat loss is {U.fmt(h)} kW ({_page_ref(heat.evidence)}); the documented cooling allowance is {U.fmt(c)} kW.",
                       constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=heat.evidence,
                       formula=f"{U.fmt(h)} kW > {U.fmt(c)} kW",
                       follow_up=FollowUp(kind="vendor", question=f"The alternate rejects {U.fmt(h)} kW against a {U.fmt(c)} kW cooling allowance. Is a lower-loss option available?"),
                       confidence=conf)
    return Finding(key="heat:cooling", topic="physical", label="cleared", title="Heat loss is within the documented cooling allowance",
                   summary=f"The alternate's heat loss is {U.fmt(h)} kW; the documented cooling allowance is {U.fmt(c)} kW.",
                   constraint=cdict, requirement_evidence=cap.evidence, supplier_evidence=heat.evidence,
                   formula=f"{U.fmt(h)} kW ≤ {U.fmt(c)} kW", scope_note="Clears the documented allowance only; other heat sources in the room are not assessed.", confidence=conf)


# ----------------------------------------------------------------------- electrical / specification
def _reactance(ctx: CaseContext) -> Optional[Finding]:
    gen = ctx.equipment_type == "generator"
    name = "xd_subtransient_pct" if gen else "impedance_pct"
    what = "Subtransient reactance Xd''" if gen else "Impedance (%Z)"
    key = "electrical:reactance" if gen else "electrical:impedance"
    spec, orig, alt = ctx.f("spec", name), ctx.f("original", name), ctx.f("alternate", name)
    if alt.status != "documented":
        if ctx.equipment_type == "unknown" and spec.status != "documented" and orig.status != "documented":
            return None
        ref_txt = ""
        ref = orig if orig.status == "documented" else spec
        if ref.status == "documented":
            ref_txt = f" The baseline is {U.fmt(float(ref.value))}%."
        return _gap_finding(
            ctx, key, "electrical", alt, what,
            f"Please state the {_lc(what)} of the alternate at rated kVA and reference temperature, with the page it appears on.{ref_txt}",
        )
    ref, ref_src = (orig, "original equipment") if orig.status == "documented" else (spec, "specification")
    a = float(alt.value)
    if ref.status != "documented":
        return Finding(
            key=key, topic="electrical", label="needs_engineer",
            title=f"{what} stated; no baseline to compare",
            summary=f"The alternate states {U.fmt(a)}% ({_page_ref(alt.evidence)}), but neither the specification nor the original equipment documents give a baseline. Engineer review needed.",
            supplier_evidence=alt.evidence,
            follow_up=FollowUp(kind="engineer", question=f"The alternate's {_lc(what)} is {U.fmt(a)}% ({_page_ref(alt.evidence)}). No baseline value was provided. Please confirm it against the impedance used in the short-circuit, coordination and arc-flash studies."),
            confidence=alt.confidence,
        )
    r = float(ref.value)
    if U.same_number(a, r, rel=1e-3):
        return None
    direction = "lower" if a < r else "higher"
    tol = (spec.detail or {}).get("tolerance_pct") if isinstance(spec.detail, dict) and spec.status == "documented" else None
    band = ""
    if tol is not None and spec.status == "documented":
        s = float(spec.value)
        within = s * (1 - tol / 100) <= a <= s * (1 + tol / 100)
        band = f" The alternate is {'within' if within else 'outside'} the specification's ±{U.fmt(tol)}% band around {U.fmt(s)}%."
    effects = (
        "Available fault current at the transformer secondary rises and downstream interrupting ratings may need re-checking; arc-flash clearing times may change."
        if (a < r and not gen)
        else "Available fault current at the transformer secondary falls, but protective-device clearing time (and so arc-flash energy) can still increase."
        if not gen
        else "Generator fault contribution and coordination inputs change."
    )
    return Finding(
        key=key, topic="electrical", label="needs_engineer",
        title=f"{what} changed: engineer review needed",
        summary=f"{what} changed from {U.fmt(r)}% ({ref_src}) to {U.fmt(a)}% ({_page_ref(alt.evidence)}), a {direction} value.{band} {effects} KNOCK-ON issues no electrical clearance.",
        requirement_evidence=ref.evidence, supplier_evidence=alt.evidence,
        formula="I_sc (infinite source, at the secondary) ∝ 1 / %Z" if not gen else None,
        computed={"baseline_pct": r, "alternate_pct": a, "ratio_alternate_to_baseline": round(a / r, 4), "direction": direction},
        follow_up=FollowUp(
            kind="engineer",
            question=(
                f"The alternate {'generator' if gen else 'transformer'}'s {_lc(what)} changed from {U.fmt(r)}% ({ref_src}) to {U.fmt(a)}% ({_page_ref(alt.evidence)}). "
                f"Please confirm whether the protection-coordination, short-circuit and arc-flash studies must be re-run, and which downstream buses need their equipment ratings re-checked."
            ),
        ),
        confidence=_min_conf(alt, ref),
    )


def _spec_findings(ctx: CaseContext) -> list[Finding]:
    out: list[Finding] = []
    spec_present = ctx.has("spec")
    if not spec_present:
        return out
    # rated kVA
    s, a = ctx.f("spec", "rated_kva"), ctx.f("alternate", "rated_kva")
    if s.status == "documented":
        if a.status != "documented":
            out.append(_gap_finding(ctx, "spec:kva", "specification", a, "Rated power (kVA)", f"Please state the rated kVA of the alternate. The specification requires {U.fmt(float(s.value))} kVA."))
        else:
            sv, av = float(s.value), float(a.value)
            if spec_deviation(s, a):
                below = av < sv
                if below or s.qualifier == "max":
                    out.append(Finding(
                        key="spec:kva", topic="specification", label="conclusive",
                        title="Alternate rating breaks the specified kVA",
                        summary=f"The alternate is rated {U.fmt(av)} kVA ({_page_ref(a.evidence)}); the specification requires {'at least ' if s.qualifier == 'min' else ''}{U.fmt(sv)} kVA ({_page_ref(s.evidence)}).",
                        requirement_evidence=s.evidence, supplier_evidence=a.evidence,
                        formula=f"{U.fmt(av)} kVA vs {U.fmt(sv)} kVA", computed={"specified_kva": sv, "alternate_kva": av},
                        follow_up=FollowUp(kind="vendor", question=f"The specification requires {U.fmt(sv)} kVA but the alternate is rated {U.fmt(av)} kVA. Please confirm the offered rating or withdraw the alternate."),
                        confidence=_min_conf(s, a)))
                else:
                    out.append(Finding(
                        key="spec:kva", topic="specification", label="needs_engineer",
                        title="Alternate rating differs from the specified kVA",
                        summary=f"The alternate is rated {U.fmt(av)} kVA; the specification states {U.fmt(sv)} kVA. A different rating changes the study inputs.",
                        requirement_evidence=s.evidence, supplier_evidence=a.evidence, computed={"specified_kva": sv, "alternate_kva": av},
                        follow_up=FollowUp(kind="engineer", question=f"The alternate is rated {U.fmt(av)} kVA against a specified {U.fmt(sv)} kVA. Please confirm whether it is acceptable and which studies it affects."),
                        confidence=_min_conf(s, a)))
    # voltages
    for fname, label_txt in (("primary_voltage_v", "primary"), ("secondary_voltage_v", "secondary")):
        s, a = ctx.f("spec", fname), ctx.f("alternate", fname)
        if s.status != "documented":
            continue
        if a.status != "documented":
            out.append(_gap_finding(ctx, f"spec:{label_txt}_voltage", "specification", a, f"{label_txt.capitalize()} voltage",
                                    f"Please state the alternate's {label_txt} voltage. The specification requires {U.fmt(float(s.value))} V."))
        elif not U.same_number(float(s.value), float(a.value), rel=1e-3):
            out.append(Finding(
                key=f"spec:{label_txt}_voltage", topic="specification", label="conclusive",
                title=f"Alternate {label_txt} voltage differs from the specification",
                summary=f"The alternate's {label_txt} voltage is {U.fmt(float(a.value))} V ({_page_ref(a.evidence)}); the specification requires {U.fmt(float(s.value))} V ({_page_ref(s.evidence)}).",
                requirement_evidence=s.evidence, supplier_evidence=a.evidence,
                formula=f"{U.fmt(float(a.value))} V ≠ {U.fmt(float(s.value))} V",
                follow_up=FollowUp(kind="vendor", question=f"The specification requires {U.fmt(float(s.value))} V {label_txt} but the alternate is {U.fmt(float(a.value))} V. Please confirm."),
                confidence=_min_conf(s, a)))
    # winding configuration
    ref = ctx.f("original", "winding_config")
    ref_src = "original equipment"
    if ref.status != "documented":
        ref, ref_src = ctx.f("spec", "winding_config"), "specification"
    a = ctx.f("alternate", "winding_config")
    if ref.status == "documented":
        if a.status != "documented":
            out.append(_gap_finding(ctx, "spec:winding", "specification", a, "Winding configuration",
                                    f"Please state the alternate's winding configuration / vector group. The baseline is {ref.value}."))
        elif str(ref.value) != str(a.value):
            out.append(Finding(
                key="spec:winding", topic="specification", label="needs_engineer",
                title="Winding configuration changed: engineer review needed",
                summary=f"The winding configuration changed from {ref.value} ({ref_src}) to {a.value} ({_page_ref(a.evidence)}). Grounding, protection and paralleling assumptions may change.",
                requirement_evidence=ref.evidence, supplier_evidence=a.evidence,
                follow_up=FollowUp(kind="engineer", question=f"The alternate's winding configuration is {a.value} against {ref.value} ({ref_src}). Please confirm grounding, protection and paralleling are unaffected."),
                confidence=_min_conf(ref, a)))
    return out


def screen(ctx: CaseContext) -> ScreenResult:
    if not ctx.has("alternate"):
        raise ValueError("screen_consequences needs an 'alternate' (supplier submittal) document")
    missing: list[str] = []
    findings: list[Finding] = []
    for fn in (_elevator, _slab, _door, _ceiling, _heat):
        f = fn(ctx, missing)
        if f is not None:
            findings.append(f)
    for f in (_reactance(ctx), *_spec_findings(ctx)):
        if f is not None:
            findings.append(f)
    conclusive = sum(f.label == "conclusive" for f in findings)
    cleared = sum(f.label == "cleared" for f in findings)
    open_n = len(findings) - conclusive - cleared
    summary = f"{conclusive} conclusive, {cleared} cleared (each for its own constraint only), {open_n} open."
    return ScreenResult(case_id=ctx.case_id, findings=findings, missing_project_facts=missing, summary=summary)
