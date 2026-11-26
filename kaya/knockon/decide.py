"""decide_and_ask: compare baseline and alternate at the same project milestone.

Answers the buyer's recovery target: yes / only_if / no_not_alone / no / needs_data. Dates are
compared at the milestone (not lead time against lead time), approvals and remediation are
included only when documented, and costs are reported only when a quote or documented estimate
backs them.
"""
from __future__ import annotations

from typing import Any, Optional

from .context import CaseContext
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

    # ---- alternate arrival (range)
    order_given = _num(sched.get("order_release_week")) is not None
    order_wk = _num(sched.get("order_release_week")) or 0.0
    appr = _num(sched.get("submittal_approval_weeks"))
    lt_min = float((lt.detail or {}).get("min", lt.value))
    lt_max = float((lt.detail or {}).get("max", lt.value))
    start = st.value if st.status == "documented" else None
    conditions: list[str] = []
    short: list[str] = []
    if start == "order":
        arr_best, arr_cons = order_wk + lt_min, order_wk + lt_max
    elif start == "approval":
        if appr is None:
            missing.append("submittal approval duration (the alternate's lead time counts from approved drawings)")
            conditions.append("the submittal approval duration is not provided; it is counted as 0 weeks in the best case")
            arr_best, arr_cons = order_wk + lt_min, order_wk + lt_max
        else:
            arr_best, arr_cons = order_wk + appr + lt_min, order_wk + appr + lt_max
    else:
        arr_best = order_wk + lt_min
        if appr is not None:
            arr_cons = order_wk + appr + lt_max
            conditions.append(f"the lead-time start condition is not stated; the best case counts from order release and the conservative case adds the {_g(appr)}-week submittal approval")
        else:
            arr_cons = order_wk + lt_max
            conditions.append("the lead-time start condition is not stated and the approval duration is unknown; the best case counts from order release")
            missing.append("submittal approval duration")
        vendor_q.append("Please state whether the quoted lead time counts from order placement or from approved drawings.")
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
    alt_ready_best = max(arr_best, route_ready or 0.0) + rem_weeks
    alt_ready_cons = max(arr_cons, route_ready or 0.0) + rem_weeks
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

    # ---- milestone
    max_other = max((w for _, w, _ in others), default=None)
    baseline_ms = max(base_sub, max_other) if max_other is not None else base_sub
    alt_ms_best = max(alt_ready_best, max_other) if max_other is not None else alt_ready_best
    alt_ms_cons = max(alt_ready_cons, max_other) if max_other is not None else alt_ready_cons
    max_rec = round(baseline_ms - alt_ms_best, 2)
    cons_rec = round(baseline_ms - alt_ms_cons, 2)
    ships_earlier = round(base_sub - arr_best, 2)
    ctrl_base = "substituted item" if max_other is None or base_sub >= max_other else max(others, key=lambda o: o[1])[0]
    if max_other is not None and base_sub >= max_other:
        ctrl_base = sub_name
    ctrl_alt_item = max(others, key=lambda o: o[1]) if others else None
    ctrl_alt = sub_name if (ctrl_alt_item is None or alt_ready_best >= ctrl_alt_item[1]) else ctrl_alt_item[0]
    milestone = MilestoneResult(
        name=ms_name, baseline_week=baseline_ms, alternate_week_best=alt_ms_best, alternate_week_conservative=alt_ms_cons,
        max_recoverable_weeks=max_rec, conservative_recoverable_weeks=cons_rec, weeks_earlier_alternate_ships=ships_earlier,
        controlling_item_baseline=ctrl_base, controlling_item_alternate=ctrl_alt, install_test_weeks=install_test,
    )

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
            open_findings = [f for f in findings if f.label not in {"conclusive", "cleared"}]
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

    return result(
        answer, headline, milestone=milestone, conditions=_uniq(conditions), requirements_to_hit_target=reqs, next_call=next_call,
        costs=costs, cost_note=cost_note, confidence=base_conf,
    )
