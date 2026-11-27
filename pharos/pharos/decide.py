"""decide_and_ask: compare baseline and alternate at the same project milestone.

Answers the buyer's recovery target: yes / only_if / no_not_alone / no / needs_data. Dates are
compared at the milestone (not lead time against lead time), approvals and remediation are
included only when documented, and costs are reported only when a quote or documented estimate
backs them.
"""
from __future__ import annotations

from typing import Any, Optional

import math

from .checks import ComparableObservation, ProductionRange, WeekFact, estimate_arrival
from .context import CaseContext
from .schedule import OpenCondition, PurchaseOrderLine, ReadyDate, assess_delivery_risk
from .schemas import (
    CompareResult,
    CostItem,
    DecisionResult,
    Finding,
    MilestoneResult,
    Requirement,
    ScreenResult,
)


def _g(x: float) -> str:
    return f"{x:g}"


def _uniq(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _ceil(x: Any) -> int:
    """Whole weeks, rounding part weeks up (the cautious direction for a delivery date)."""
    return max(0, int(math.ceil(float(x) - 1e-9)))


def _src(evs: list) -> str:
    if not evs:
        return ""
    e = evs[0]
    return f"{e.document}{', rev ' + e.revision if e.revision else ''} p.{e.page}: {e.quote}"[:400]


def _blocker_phrase(f: Finding) -> str:
    return {
        "weight:elevator": "the elevator route blocked",
        "dims:door": "the door route blocked",
        "dims:ceiling": "the overhead clearance exceeded",
        "weight:slab": "the floor loading limit exceeded",
        "heat:cooling": "the cooling allowance exceeded",
    }.get(f.key, f"'{f.title.lower()}' unresolved")


def _collect_questions(findings: list[Finding]) -> tuple[list[str], list[str], list[str]]:
    vendor, eng, copy = [], [], []
    for f in findings:
        q = f.follow_up.question
        if not q:
            continue
        if f.follow_up.kind in {"vendor", "route"}:
            vendor.append(q)
        elif f.follow_up.kind == "engineer":
            eng.append(q)
        elif f.follow_up.kind == "readable_copy":
            copy.append(q)
    return _uniq(vendor), _uniq(eng), _uniq(copy)


def decide(ctx: CaseContext, screen_res: ScreenResult, cmp_res: CompareResult) -> DecisionResult:
    findings = screen_res.findings
    settled = [f.key for f in findings if f.label in {"conclusive", "cleared"}]
    open_keys = [f.key for f in findings if f.label not in {"conclusive", "cleared"}]
    vendor_q, eng_q, copy_q = _collect_questions(findings)
    missing = list(screen_res.missing_project_facts)
    sched = ctx.schedule
    target = ctx.target
    lt = ctx.f("alternate", "lead_time_weeks")
    st = ctx.f("alternate", "lead_time_start")
    refs = [d.ref() for d in ctx.docs.values()]
    confs = [f.confidence for f in findings if f.confidence > 0]
    base_conf = round(min(confs), 2) if confs else 0.6

    def result(answer: str, headline: str, **kw: Any) -> DecisionResult:
        return DecisionResult(
            case_id=ctx.case_id, version=0, inputs_hash=ctx.inputs_hash, target_weeks=target, answer=answer,  # type: ignore[arg-type]
            headline=headline, settled=settled, open=open_keys, findings=findings,
            vendor_questions=_uniq(vendor_q), engineer_questions=_uniq(eng_q), readable_copy_requests=_uniq(copy_q),
            missing_project_facts=_uniq(missing), documents=refs, **kw,
        )

    # ---- needs data: lead time of the alternate
    if lt.status != "documented":
        if lt.status == "could_not_read":
            copy_q.append(f"The quoted lead time could not be read (page(s) {lt.unreadable_pages}). Please send a text-based copy or state the lead time and its start condition.")
            why = "The alternate's quoted lead time could not be read."
        elif lt.status == "conflicting":
            vendor_q.append("The submittal gives conflicting lead times. Please confirm one lead time and whether it counts from order placement or from approved drawings.")
            why = "The alternate's submittal gives conflicting lead times."
        else:
            vendor_q.append("Please state the quoted lead time and whether it counts from order placement or from approved drawings.")
            why = "The alternate's quoted lead time is not stated."
        return result("needs_data", f"Cannot say how many weeks this swap recovers. {why}", conditions=[],
                      cost_note="", confidence=0.3)

    # ---- needs data: schedule
    items = (sched or {}).get("items") if isinstance(sched, dict) else None
    if not sched or not isinstance(items, list) or not items:
        missing.append("project schedule: baseline arrival week of the substituted item and the arrival weeks of the other items the milestone needs")
        return result(
            "needs_data",
            "Milestone dates and controlling items are needed to say how many weeks this swap can recover. "
            "Provide the baseline arrival week of the substituted item and the arrival weeks of the other items the milestone depends on.",
            conditions=[], cost_note="", confidence=0.3,
        )
    sub_id = sched.get("substituted_item")
    sub = next((i for i in items if i.get("id") == sub_id), None) or next((i for i in items if i.get("role") == "substitution"), None)
    base_sub = _num((sub or {}).get("baseline_arrival_week", (sub or {}).get("arrival_week")))
    if sub is None or base_sub is None:
        missing.append("baseline arrival week of the substituted item")
        return result("needs_data", "The schedule does not give the baseline arrival week of the substituted item.", conditions=[], cost_note="", confidence=0.3)

    sub_name = str(sched.get("substituted_item_label") or sub.get("name") or "substituted item")
    others: list[tuple[str, float, Optional[str]]] = []
    unknown_items: list[str] = []
    for it in items:
        if it is sub or it.get("requires") is False:
            continue
        w = _num(it.get("arrival_week", it.get("baseline_arrival_week")))
        if w is not None:
            others.append((str(it.get("name") or it.get("id")), w, it.get("vendor")))
        else:
            unknown_items.append(str(it.get("name") or it.get("id")))
    if unknown_items:
        for n in unknown_items:
            missing.append(f"arrival week of '{n}' (the milestone needs it; set requires=false if it does not)")
        return result(
            "needs_data",
            f"The schedule gives no arrival week for {', '.join(unknown_items)}, which the {str((sched.get('milestone') or {}).get('name') or 'milestone').lower()} needs. "
            "Without it the controlling item, and so the weeks the swap can recover, cannot be stated.",
            conditions=[], cost_note="", confidence=0.3,
        )
    ms_cfg = sched.get("milestone") or {}
    ms_name = str(ms_cfg.get("name") or "Milestone")
    install_test = _num(ms_cfg.get("install_test_weeks"))

    # ---- alternate arrival window, through the deterministic estimate_arrival
    order_given = _num(sched.get("order_release_week")) is not None
    order_wk = _num(sched.get("order_release_week")) or 0.0
    appr = _num(sched.get("submittal_approval_weeks"))
    transit = _num(sched.get("transit_weeks"))
    lt_min = float((lt.detail or {}).get("min", lt.value))
    lt_max = float((lt.detail or {}).get("max", lt.value))
    start = st.value if st.status == "documented" else None
    conditions: list[str] = []
    short: list[str] = []
    lt_src = _src(lt.evidence)
    pr = ProductionRange(minimum=_ceil(lt_min), maximum=_ceil(lt_max), source=lt_src)  # part weeks round up
    tw = WeekFact(value=_ceil(transit or 0), source="schedule: transit_weeks" if transit is not None else "not provided; taken as 0")
    ow = WeekFact(value=_ceil(order_wk), source="schedule: order_release_week" if order_given else "not provided; taken as week 0")
    obs_raw = (ctx.facts.get("arrival_observations") or (sched or {}).get("arrival_observations") or [])
    observations = [ComparableObservation(quoted_weeks=_ceil(o["quoted_weeks"]), actual_weeks=_ceil(o["actual_weeks"]), source=str(o.get("source") or "observation")) for o in obs_raw if isinstance(o, dict) and o.get("quoted_weeks") and o.get("actual_weeks") is not None]
    a_order = estimate_arrival(pr, tw, start="order", order_week=ow, comparable_observations=observations)
    a_appr = estimate_arrival(pr, tw, approval_week=WeekFact(value=_ceil(order_wk + appr), source="schedule: order release plus submittal approval"), comparable_observations=observations) if appr is not None else None
    if start == "order":
        arrival = a_order
        arr_best, arr_cons = arrival.onsite_week_range
    elif start == "approval":
        if a_appr is None:
            missing.append("submittal approval duration (the alternate's lead time counts from approved drawings)")
            conditions.append("the submittal approval duration is not provided; it is counted as 0 weeks in the best case")
            arrival = a_order
        else:
            arrival = a_appr
        arr_best, arr_cons = arrival.onsite_week_range
    else:
        arrival = a_order
        arr_best = a_order.onsite_week_range[0]
        if a_appr is not None:
            arr_cons = a_appr.onsite_week_range[1]
            conditions.append(f"the lead-time start condition is not stated; the best case counts from order release and the conservative case adds the {_g(appr)}-week submittal approval")
        else:
            arr_cons = a_order.onsite_week_range[1]
            conditions.append("the lead-time start condition is not stated and the approval duration is unknown; the best case counts from order release")
            missing.append("submittal approval duration")
        vendor_q.append("Please state whether the quoted lead time counts from order placement or from approved drawings.")
    if arrival.reference is not None:
        ref_hi = (arrival.reference_onsite_week_range or (arr_best, arr_cons))[1]
        if ref_hi > arr_cons:
            arr_cons = ref_hi
        conditions.append(f"comparable delivered orders ({arrival.reference.observations}) slipped between {arrival.reference.slip_ratio_min:g}x and {arrival.reference.slip_ratio_max:g}x of their quotes; the conservative window allows for that observed spread")
    elif arrival.reference_note:
        conditions.append(arrival.reference_note)
    if lt_max > lt_min:
        conditions.append(f"the quoted lead time is a range ({_g(round(lt_min, 1))}–{_g(round(lt_max, 1))} weeks)")

    # ---- route and remediation
    blockers = [f for f in findings if f.label == "conclusive"]
    phys_blockers = [f for f in blockers if f.topic == "physical"]
    routes = [r for r in (sched.get("alternate_routes") or []) if _num(r.get("ready_week")) is not None]

    def route_for(f: Finding) -> Optional[float]:
        ready = [float(r["ready_week"]) for r in routes if f.topic == "physical" and (not r.get("resolves") or f.key in r["resolves"])]
        return min(ready) if ready else None

    route_ready = max((route_for(f) or 0.0 for f in phys_blockers if route_for(f) is not None), default=None)
    rem_weeks = 0.0
    costs: list[CostItem] = []
    for r in sched.get("remediation") or []:
        w = _num(r.get("weeks"))
        if w and r.get("affects") in (None, "substituted_item", sub.get("id")):
            rem_weeks += w
        c = r.get("cost")
        if isinstance(c, dict) and _num(c.get("amount")) is not None and c.get("source"):
            costs.append(CostItem(item=str(r.get("description", "remediation")), amount=float(c["amount"]), currency=str(c.get("currency", "")), source=str(c["source"])))
    unresolved = [f for f in blockers if not (f.topic == "physical" and route_for(f) is not None)]
    open_findings = [f for f in findings if f.label not in {"conclusive", "cleared"}]
    alt_ready_best = _ceil(max(arr_best, route_ready or 0.0) + rem_weeks)
    alt_ready_cons = _ceil(max(arr_cons, route_ready or 0.0) + rem_weeks)
    if route_ready is not None:
        conditions.append(f"the documented alternative route is ready in week {_g(route_ready)}")
    if rem_weeks:
        conditions.append(f"documented remediation adds {_g(rem_weeks)} week(s)")
    if unresolved:
        titles = "; ".join(f.title for f in unresolved)
        conditions.insert(0, f"unresolved: {titles}")
        short.append("the delivery route is resolved in time" if any(f.topic == "physical" for f in unresolved) else "the conclusive deviation is resolved")
    if not order_given:
        conditions.append("the order release week was not provided; it is taken as project week 0")
    conditions.append("installation and testing durations are unchanged")
    short.append("installation and testing durations are unchanged")

    # ---- the shared schedule engine: baseline ranking and the substitution scenario, best and conservative
    sched_src = ctx.docs["schedule"].name if "schedule" in ctx.docs else "project facts: schedule"
    base_lines: list[PurchaseOrderLine] = []
    for it in items:
        if it.get("requires") is False:
            continue
        w = _num(it.get("arrival_week", it.get("baseline_arrival_week")))
        base_lines.append(PurchaseOrderLine(line_id=str(it.get("id") or it.get("name")), baseline=ReadyDate(week=_ceil(w or 0), source=f"{sched_src}, item {it.get('id') or it.get('name')}")))
    sub_line_id = str(sub.get("id") or sub.get("name"))
    post = WeekFact(value=_ceil(install_test or 0), source=f"{sched_src}: milestone install_test_weeks" if install_test is not None else "not provided; taken as 0 (only differences between scenarios are meaningful)")
    tgt = WeekFact(value=_ceil(target), source="requested recovery target") if target is not None and target > 0 else None
    conds = [OpenCondition(description=f.title, source=_src(f.supplier_evidence or f.requirement_evidence) or f.key) for f in (unresolved + open_findings)]

    def run_engine(week: int, lines_override: Optional[dict[str, ReadyDate]] = None):
        lines = []
        for ln in base_lines:
            prop = None
            if ln.line_id == sub_line_id:
                prop = ReadyDate(week=week, source=lt_src, open_conditions=conds)
            elif lines_override and ln.line_id in lines_override:
                prop = lines_override[ln.line_id]
            lines.append(PurchaseOrderLine(line_id=ln.line_id, baseline=ln.baseline, proposed=prop))
        return assess_delivery_risk(lines, post, recovery_target_weeks=tgt)

    eng_best = run_engine(alt_ready_best)
    eng_cons = run_engine(alt_ready_cons)
    baseline_ms = float(eng_best.baseline.handoff_week)
    alt_ms_best = float(eng_best.proposed.handoff_week)
    alt_ms_cons = float(eng_cons.proposed.handoff_week)
    max_rec = float(eng_best.potential_recovery_weeks)
    cons_rec = float(eng_cons.potential_recovery_weeks)
    base_sub = float(next(l.baseline.week for l in base_lines if l.line_id == sub_line_id))
    ships_earlier = float(base_sub - _ceil(arr_best))
    names = {str(it.get("id") or it.get("name")): str(it.get("name") or it.get("id")) for it in items}
    vendors = {str(it.get("id") or it.get("name")): it.get("vendor") for it in items}
    others = [(names[l.line_id], float(l.baseline.week), vendors[l.line_id]) for l in base_lines if l.line_id != sub_line_id]
    max_other = max((w for _, w, _ in others), default=None)
    ctrl_base_ids = eng_best.baseline.controlling_line_ids
    ctrl_base = " and ".join(names[i] if i != sub_line_id else sub_name for i in ctrl_base_ids) or sub_name
    ctrl_alt_item = max(others, key=lambda o: o[1]) if others else None
    alt_ctrl_ids = eng_best.proposed.controlling_line_ids
    ctrl_alt = sub_name if (ctrl_alt_item is None or sub_line_id in alt_ctrl_ids and alt_ready_best >= ctrl_alt_item[1]) else ctrl_alt_item[0]
    milestone = MilestoneResult(
        name=ms_name, baseline_week=baseline_ms, alternate_week_best=alt_ms_best, alternate_week_conservative=alt_ms_cons,
        max_recoverable_weeks=max_rec, conservative_recoverable_weeks=cons_rec, weeks_earlier_alternate_ships=ships_earlier,
        controlling_item_baseline=ctrl_base, controlling_item_alternate=ctrl_alt, install_test_weeks=install_test,
    )
    ranking = [
        {"line_id": r.line_id, "name": names.get(r.line_id, r.line_id), "ready_week": r.ready.week, "float_to_handoff_weeks": r.float_to_handoff_weeks,
         "margin_to_deadline_weeks": r.margin_to_deadline_weeks, "action": r.action, "owner": vendors.get(r.line_id)}
        for r in eng_best.baseline.lines_by_urgency
    ]

    if ships_earlier > 0:
        ships_txt = f"The alternate ships {_g(ships_earlier)} weeks earlier"
    elif ships_earlier == 0:
        ships_txt = "The alternate ships in the same week"
    else:
        ships_txt = f"The alternate ships {_g(-ships_earlier)} weeks later"
    assump = ", ".join(short[:-1]) + (" and " if len(short) > 1 else "") + short[-1] if short else ""
    rec_txt = (f"the most this swap can recover is {_g(max_rec)} weeks" if max_rec >= 0
               else f"this swap would make the milestone {_g(-max_rec)} weeks later")
    potential = ""
    if unresolved and any(f.topic == "physical" for f in unresolved):
        phr = " and ".join(_blocker_phrase(f) for f in unresolved if f.topic == "physical")
        potential = f" With {phr} and no dated alternative, {_g(max_rec)} weeks is potential recovery, not a promised saving."
    cost_note = ""
    if phys_blockers and not costs:
        cost_note = "Cost of resolving the blocked constraint is unknown: no quote or documented estimate was provided. Request a quote."
    elif costs:
        cost_note = "Costs shown are only those backed by the quote or documented estimate cited."

    reqs: list[Requirement] = []
    answer: str
    headline: str
    if target is None or target <= 0:
        ctrl_txt = f" {ctrl_alt} (week {_g(ctrl_alt_item[1])}) controls the {ms_name.lower()} milestone." if (ctrl_alt_item and ctrl_alt != sub_name) else ""
        answer = "no_target"
        headline = (f"Against the week-{_g(baseline_ms)} baseline, {rec_txt}, assuming {assump}.{ctrl_txt}{potential} "
                    "Set a recovery target to get a yes or no.")
    else:
        needed = baseline_ms - target
        alt_ok = alt_ready_best <= needed + 1e-9 and needed >= 0
        for name, w, vendor in others:
            if needed >= 0 and w > needed + 1e-9:
                reqs.append(Requirement(item=name, currently_week=w, must_be_ready_by_week=round(needed, 2), owner=vendor))
        if alt_ok and not reqs:
            cons_miss = alt_ready_cons > needed + 1e-9
            if unresolved or cons_miss or open_findings:
                answer = "only_if"
                need = list(short[:-1])
                if cons_miss:
                    need.append("the vendor delivers at the low end of its quoted lead-time range")
                if open_findings:
                    need.append("the open items are resolved without adding time (" + "; ".join(f.title for f in open_findings) + ")")
                    conditions.append("open items still to resolve: " + "; ".join(f.title for f in open_findings))
                need_txt = " and ".join(need) if need else "the stated conditions hold"
                headline = f"Only if {need_txt}. {rec_txt[0].upper() + rec_txt[1:]}, against a {_g(target)}-week target.{potential}"
            else:
                answer = "yes"
                headline = (f"Yes. {ships_txt} and the {ms_name.lower()} milestone can move {_g(max_rec)} weeks earlier, "
                            f"meeting the {_g(target)}-week target, assuming {assump}.")
        elif alt_ok and reqs:
            answer = "no_not_alone"
            req_txt = " and ".join(f"{r.item} must also be ready by week {_g(r.must_be_ready_by_week)}" for r in reqs)
            headline = (f"No, not from the {sub_name} swap alone. {ships_txt}, but {ctrl_alt} is still due in week {_g(ctrl_alt_item[1]) if ctrl_alt_item else _g(alt_ready_best)}. "
                        f"Against the week-{_g(baseline_ms)} baseline, {rec_txt}, assuming {assump}. "
                        f"To recover {_g(target)} weeks, {req_txt}.{potential}")
        elif needed < 0:
            answer = "no"
            headline = f"No. A {_g(target)}-week recovery is longer than the whole baseline (week {_g(baseline_ms)}), so it cannot be reached by any substitution."
        else:
            answer = "no"
            headline = (f"No. Even in the best case the alternate is ready in week {_g(alt_ready_best)}; a {_g(target)}-week recovery needs it by week {_g(needed)}.{potential}")

    next_call: Optional[dict[str, str]] = None
    if reqs:
        r = reqs[0]
        next_call = {"party": r.owner or r.item, "why": f"{r.item} must be ready by week {_g(r.must_be_ready_by_week)} to reach the {_g(target or 0)}-week target"}
    elif unresolved:
        next_call = {"party": f"{sub_name} vendor", "why": unresolved[0].follow_up.question or unresolved[0].title}
    elif eng_q:
        next_call = {"party": "Engineer of record", "why": "open electrical review questions (see engineer questions)"}

    # ---- recovery options compared at the same milestone: substitute, priced expedites, and the combination
    def meets(res) -> Optional[bool]:
        st = res.recovery_target_status
        return None if st is None else (True if st in {"met_on_stated_dates", "conditional_on_open_items"} else False if st == "not_met" else None)

    def cost_of(parts: list[Optional[dict]]) -> tuple[Optional[dict], str]:
        if parts and all(p is not None for p in parts):
            cur = {p["currency"] for p in parts}
            if len(cur) == 1:
                return {"amount": sum(p["amount"] for p in parts), "currency": cur.pop(), "sources": [p["source"] for p in parts]}, "Sum of the documented quotes cited; nothing else is included."
        return None, "Incremental cost is not documented in full: request a quote. No price is assumed."

    def sub_cost() -> Optional[dict]:
        """Documented extra cost of the substitution: its sourced price difference plus any sourced remediation cost."""
        sc = sched.get("substitution_cost")
        if not (isinstance(sc, dict) and _num(sc.get("amount")) is not None and sc.get("source")):
            return None
        parts = [{"amount": float(sc["amount"]), "currency": str(sc.get("currency", "")), "source": str(sc["source"])}] + \
                [{"amount": c.amount, "currency": c.currency, "source": c.source} for c in costs]
        if len({p["currency"] for p in parts}) != 1:
            return None
        return {"amount": sum(p["amount"] for p in parts), "currency": parts[0]["currency"], "sources": [p["source"] for p in parts]}

    sub_conditions = [c.description for c in conds]
    sub_next = (unresolved[0].follow_up.question if unresolved and unresolved[0].follow_up.question else
                (open_findings[0].follow_up.question if open_findings and open_findings[0].follow_up.question else None))
    options: list[dict[str, Any]] = [{
        "id": "substitute", "type": "substitute", "description": f"Take the alternate {sub_name}", "line": sub_line_id,
        "ready_week": alt_ready_best, "recovery_weeks_best": max_rec, "recovery_weeks_conservative": cons_rec,
        "target_status": eng_best.recovery_target_status, "meets_target": meets(eng_best), "conditions": sub_conditions,
        "incremental_cost": sub_cost(), "cost_note": "Sum of the documented quotes cited; nothing else is included." if sub_cost() else "The price difference of the alternate is not documented (give a sourced substitution_cost): request a quote. No price is assumed.",
        "owner": f"{sub_name} vendor", "next_action": sub_next,
    }]
    expedites = [o for o in (sched.get("options") or []) if isinstance(o, dict) and o.get("type") == "expedite" and str(o.get("line")) in names and _num(o.get("new_week")) is not None]

    def ready_for(o: dict) -> ReadyDate:
        return ReadyDate(
            week=_ceil(o["new_week"]), source=str(o.get("source") or f"{sched_src}, option {o.get('id')}"),
            open_conditions=[OpenCondition(description=str(c.get("description", "condition")), source=str(c.get("source") or "option")) for c in (o.get("conditions") or []) if isinstance(c, dict)],
        )

    def prem(o: dict) -> Optional[dict]:
        pr_ = o.get("premium")
        return {"amount": float(pr_["amount"]), "currency": str(pr_.get("currency", "")), "source": str(pr_["source"])} if isinstance(pr_, dict) and _num(pr_.get("amount")) is not None and pr_.get("source") else None

    for o in expedites:
        eng = assess_delivery_risk([PurchaseOrderLine(line_id=l.line_id, baseline=l.baseline, proposed=ready_for(o) if l.line_id == str(o["line"]) else None) for l in base_lines], post, recovery_target_weeks=tgt)
        cost, note = cost_of([prem(o)])
        options.append({
            "id": str(o.get("id") or f"expedite-{o['line']}"), "type": "expedite", "description": str(o.get("description") or f"Expedite {names[str(o['line'])]}"),
            "line": str(o["line"]), "ready_week": _ceil(o["new_week"]), "recovery_weeks_best": float(eng.potential_recovery_weeks), "recovery_weeks_conservative": float(eng.potential_recovery_weeks),
            "target_status": eng.recovery_target_status, "meets_target": meets(eng), "conditions": [c.description for c in ready_for(o).open_conditions],
            "incremental_cost": cost, "cost_note": note, "owner": vendors.get(str(o["line"])) or names[str(o["line"])],
            "next_action": f"Ask {vendors.get(str(o['line'])) or names[str(o['line'])]} to commit in writing to week {_ceil(o['new_week'])}" + (f" at the quoted premium" if cost else " and to quote the premium"),
        })
    if expedites:
        over = {str(o["line"]): ready_for(o) for o in expedites}
        eb, ec = run_engine(alt_ready_best, over), run_engine(alt_ready_cons, over)
        cost, note = cost_of([prem(o) for o in expedites] + ([sub_cost()] if sched.get("substitution_cost") else []))
        options.append({
            "id": "substitute+expedite", "type": "combined", "description": f"Take the alternate {sub_name} and expedite " + ", ".join(names[k] for k in over),
            "line": sub_line_id, "ready_week": alt_ready_best, "recovery_weeks_best": float(eb.potential_recovery_weeks), "recovery_weeks_conservative": float(ec.potential_recovery_weeks),
            "target_status": eb.recovery_target_status, "meets_target": meets(eb), "conditions": sub_conditions + [c.description for ex in over.values() for c in ex.open_conditions],
            "incremental_cost": cost, "cost_note": note, "owner": "several parties", "next_action": "Both the substitution conditions and the expedite commitments must be resolved.",
        })
    viable = [o for o in options if o["meets_target"]]
    recommendation: Optional[str] = None
    if tgt is None:
        recommendation = "Set a recovery target to compare the options against it."
    elif viable:
        best = sorted(viable, key=lambda o: (-o["recovery_weeks_best"], len(o["conditions"]), (o["incremental_cost"] or {}).get("amount", float("inf"))))[0]
        c = best["incremental_cost"]
        recommendation = (f"Recommended: {best['description']}. It recovers up to {_g(best['recovery_weeks_best'])} weeks against a {_g(target)}-week target"
                          + (f", with {len(best['conditions'])} open condition(s)" if best["conditions"] else "")
                          + (f"; documented extra cost {c['amount']:,.0f} {c['currency']} ({'; '.join(c['sources']) if 'sources' in c else c['source']})." if c else "; extra cost is not documented, so request a quote."))
    else:
        recommendation = "No option on the table reaches the target. " + (f"Closest: {sorted(options, key=lambda o: -o['recovery_weeks_best'])[0]['description']} at {_g(sorted(options, key=lambda o: -o['recovery_weeks_best'])[0]['recovery_weeks_best'])} weeks." if options else "")

    return result(
        answer, headline, milestone=milestone, conditions=_uniq(conditions), requirements_to_hit_target=reqs, next_call=next_call,
        costs=costs, cost_note=cost_note, confidence=base_conf,
        options=options, ranking=ranking, recommendation=recommendation, arrival=arrival.model_dump(mode="json"),
    )
