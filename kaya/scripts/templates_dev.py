"""Document layouts used for the DEVELOPMENT sample packages (A, B, C, spec S, logistics L)."""
from __future__ import annotations

from typing import Any

SYN = "(synthetic sample document - fictional vendor)"


def _f(n: float, d: int = 0) -> str:
    return f"{n:,.{d}f}"


def _kv(v: float) -> str:
    return f"{v/1000:g} kV"


def tpl_a(d: dict[str, Any]) -> list[list[tuple]]:
    """Vendor datasheet, SI table."""
    rows = [["Item", "Value"]]
    if "kva" in d:
        rows.append(["Rated power (ONAN)", f"{_f(d['kva'])} kVA"])
    if "pri_v" in d:
        rows.append(["Primary voltage", f"{_kv(d['pri_v'])} Delta"])
    if "sec_v" in d:
        rows.append(["Secondary voltage", "480Y/277 V" if d["sec_v"] == 480 else f"{_f(d['sec_v'])} V"])
    if "z_pct" in d:
        rows.append(["Impedance (%Z) at 75 C", f"{d['z_pct']:.2f} %"])
    if "xd_pct" in d:
        rows.append(["Subtransient reactance Xd\"", f"{d['xd_pct']:.1f} %"])
    if "vec" in d:
        rows.append(["Vector group", d["vec"]])
    if "dims" in d:
        L, W, H = d["dims"]
        rows.append(["Overall dimensions (L x W x H)", f"{_f(L)} x {_f(W)} x {_f(H)} mm"])
    for label, kg in d.get("sections", []):
        rows.append([f"Shipping weight - {label}", f"{_f(kg)} kg"])
    if "total_kg" in d:
        rows.append(["Total weight (with oil)", f"{_f(d['total_kg'])} kg"])
    if "heat_kw" in d:
        rows.append(["Total losses at rated load", f"{d['heat_kw']:.1f} kW"])
    if "lead_max" in d:
        start = {"order": " ARO", "approval": " ARA", None: ""}[d.get("start")]
        rows.append(["Lead time", f"{d['lead_max']:g} weeks{start}"])
    head = [("h", f"{d.get('title', 'EQUIPMENT SUBMITTAL DATA SHEET')} {SYN}")]
    if "mfr" in d:
        head.append(("p", f"Manufacturer: {d['mfr']}"))
    if "model" in d:
        head.append(("p", f"Model: {d['model']}"))
    if "rev" in d:
        head.append(("p", f"Revision: {d['rev']}"))
    return [head + [("sp", 6), ("table", rows, [220, 260])], [("h", "General notes"), ("p", "Data are for submittal review. Dimensions and weights are approximate; certified drawings follow approval.")]]


def tpl_b(d: dict[str, Any]) -> list[list[tuple]]:
    """Technical proposal, key: value lines."""
    lines: list[tuple] = [("h", f"TECHNICAL PROPOSAL {SYN}")]
    if "mfr" in d:
        lines.append(("p", f"Make: {d['mfr']}"))
    if "model" in d:
        lines.append(("p", f"Type designation: {d['model']}"))
    if "rev" in d:
        lines.append(("p", f"Proposal revision: {d['rev']}"))
    if "kva" in d:
        lines.append(("p", f"Capacity: {d['kva']/1000:g} MVA"))
    if "pri_v" in d and "sec_v" in d:
        lines.append(("p", f"Voltage ratio: {_f(d['pri_v'])} V - {'480Y/277' if d['sec_v']==480 else _f(d['sec_v'])} V"))
    if "z_pct" in d:
        lines.append(("p", f"Percent impedance: {d['z_pct']:.2f} %"))
    if "xd_pct" in d:
        lines.append(("p", f"Subtransient reactance (Xd''): {d['xd_pct']:.1f} %"))
    if "family" in d:
        lines.append(("p", "Connection: " + {"delta-wye": "Delta - Grounded Wye", "delta-delta": "Delta - Delta", "wye-wye": "Wye - Wye", "wye-delta": "Wye - Delta"}[d["family"]]))
    if "dims" in d:
        L, W, H = d["dims"]
        lines.append(("p", f"Dimensions (W x D x H): {_f(W)} x {_f(L)} x {_f(H)} mm"))
    for label, kg in d.get("sections", []):
        lines.append(("p", f"Heaviest shipping section ({label}): {_f(kg)} kg"))
    if "total_kg" in d:
        lines.append(("p", f"Operating weight: {_f(d['total_kg'])} kg"))
    if "noload_kw" in d:
        lines.append(("p", f"No-load loss: {d['noload_kw']:.1f} kW"))
    if "load_kw" in d:
        lines.append(("p", f"Load loss: {d['load_kw']:.1f} kW"))
    if "heat_kw" in d and "noload_kw" not in d:
        lines.append(("p", f"Heat rejection: {d['heat_kw']:.1f} kW"))
    if "lead_max" in d:
        tail = {"order": " from receipt of purchase order", "approval": " after approved drawings", None: ""}[d.get("start")]
        lines.append(("p", f"Delivery: {d['lead_max']:g} weeks{tail}"))
    return [lines]


def tpl_c(d: dict[str, Any]) -> list[list[tuple]]:
    """Quotation with narrative sentences and one measurement per line."""
    p1: list[tuple] = [("h", f"QUOTATION {SYN}")]
    if "mfr" in d:
        p1.append(("p", f"Supplier: {d['mfr']}"))
    if "model" in d:
        p1.append(("p", f"Model number: {d['model']}"))
    if "rev" in d:
        p1.append(("p", f"Rev. {d['rev']}"))
    if "kva" in d and "pri_v" in d and "sec_v" in d:
        fam = {"delta-wye": "delta-wye", "delta-delta": "delta-delta", "wye-wye": "wye-wye", "wye-delta": "wye-delta"}.get(d.get("family", ""), "")
        p1.append(("p", f"The offered unit is rated {_f(d['kva'])} kVA, {_kv(d['pri_v'])} / {'480Y/277' if d['sec_v']==480 else _f(d['sec_v'])} V."))
    elif "kva" in d:
        p1.append(("p", f"The offered unit is rated {_f(d['kva'])} kVA."))
    if "family" in d:
        p1.append(("p", "Winding connection: " + {"delta-wye": "Dyn11 (delta primary, grounded wye secondary)", "delta-delta": "Dd0", "wye-wye": "Yyn0", "wye-delta": "Yd1"}[d["family"]]))
    if "z_pct" in d:
        p1.append(("p", f"Impedance voltage: {d['z_pct']:.2f} % at 85 C reference."))
    if "xd_pct" in d:
        p1.append(("p", f"Subtransient reactance Xd'' = {d['xd_pct']:.1f} %."))
    p2: list[tuple] = [("h", "Physical data")]
    if "dims" in d:
        L, W, H = d["dims"]
        p2 += [("p", f"Length: {_f(L)} mm"), ("p", f"Width: {_f(W)} mm"), ("p", f"Height: {_f(H)} mm")]
    for label, kg in d.get("sections", []):
        p2.append(("p", f"Shipping section - {label}: {_f(kg)} kg"))
    if "total_kg" in d:
        p2.append(("p", f"Total weight: {_f(d['total_kg'])} kg"))
    if "heat_kw" in d:
        p2.append(("p", f"Total heat loss: {d['heat_kw']:.1f} kW"))
    if "lead_max" in d:
        tail = {"order": " ARO", "approval": " after approval of drawings", None: ""}[d.get("start")]
        p2.append(("p", f"Lead time: {d['lead_max']:g} weeks{tail}"))
    return [p1, p2]


def tpl_spec(d: dict[str, Any]) -> list[list[tuple]]:
    """Buyer specification (requirements voice)."""
    rows = [["Requirement", "Value"]]
    if "kva" in d:
        rows.append(["Rated power (ONAN)", f"not less than {_f(d['kva'])} kVA"])
    if "pri_v" in d:
        rows.append(["Primary voltage", f"{_kv(d['pri_v'])}, delta"])
    if "sec_v" in d:
        rows.append(["Secondary voltage", "480Y/277 V" if d["sec_v"] == 480 else f"{_f(d['sec_v'])} V"])
    if "z_pct" in d:
        rows.append(["Impedance", f"{d['z_pct']:.2f} % (tolerance +/-{d.get('tol', 7.5):g} %)"])
    if "xd_pct" in d:
        rows.append(["Subtransient reactance Xd\"", f"{d['xd_pct']:.1f} % maximum"])
    if "vec" in d:
        rows.append(["Winding connection", d["vec"]])
    if "heat_kw" in d:
        rows.append(["Total losses", f"{d['heat_kw']:.1f} kW maximum"])
    head = [("h", f"{d.get('title', 'SECTION 26 12 00 - TRANSFORMER')} {SYN}"), ("p", f"Revision: {d.get('rev', 'A')}"), ("sp", 6), ("table", rows, [200, 280])]
    return [head, [("h", "Substitutions"), ("p", "Requests for substitution shall state all deviations from the values above.")]]


def tpl_logistics(d: dict[str, Any]) -> list[list[tuple]]:
    rows = [["Constraint", "Value"]]
    if "elevator_kg" in d:
        rows.append(["Freight elevator capacity", f"{_f(d['elevator_kg'])} kg"])
    if "door" in d:
        rows.append(["Delivery door clear opening (W x H)", f"{_f(d['door'][0])} x {_f(d['door'][1])} mm"])
    if "slab" in d:
        rows.append(["Floor loading limit", f"{_f(d['slab'])} kg/m2"])
    if "cooling_kw" in d:
        rows.append(["Cooling capacity available for this unit", f"{d['cooling_kw']:g} kW"])
    if "ceiling" in d:
        rows.append(["Overhead clearance (ceiling)", f"{_f(d['ceiling'])} mm"])
    return [[("h", f"DELIVERY AND RIGGING PLAN {SYN}"), ("p", "Revision: 1"), ("sp", 6), ("table", rows, [250, 230])]]
