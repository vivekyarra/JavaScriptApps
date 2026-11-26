"""Unfamiliar layouts for the MILESTONE packages. Written after the dev templates were frozen."""
from __future__ import annotations

from typing import Any

SYN = "(synthetic sample document - fictional vendor)"


def tpl_harbor(d: dict[str, Any]) -> list[list[tuple]]:
    """Imperial quotation: values in narrative lines, units in table headers, dot leaders."""
    x = d["disp"]
    p1: list[tuple] = [("h", f"HARBOR ELECTRIC - TRANSFORMER QUOTATION {SYN}"),
                       ("p", f"Supplier: {d['mfr']}"), ("p", f"Catalog No.: {d['model']}"),
                       ("p", f"Quote revision {d['rev']} dated 2026-10-02"),
                       ("p", f"Nameplate rating: {d['kva']:,} kVA, three phase, 60 Hz"),
                       ("p", f"Voltages: {x['pri']} delta primary / 480Y/277 V grounded wye secondary"),
                       ("p", f"Z% @ 85C . . . . {d['z_pct']:.2f}"),
                       ("p", "Phase relationship: Delta-Wye, 30 degree lag")]
    p2: list[tuple] = [("h", "Weights and dimensions"),
                       ("table", [["Item", "Value"],
                                  ["Overall size (in)", x["size"]],
                                  ["Weight, core and coil - ships separately (lb)", x["heaviest"]],
                                  ["Total weight, filled (lb)", x["total"]],
                                  ["Total losses (kW)", f"{d['heat_kw']:.1f}"],
                                  ["Delivery (ex-works)", x["lead"]]], [260, 220])]
    return [p1, p2]


def tpl_harbor_logistics(d: dict[str, Any]) -> list[list[tuple]]:
    rows = [["Site item", "Limit"],
            ["Service elevator rated load", "7,500 lb"],
            ["Slab design live load", "250 psf"],
            ["Door clear opening", "96 in wide x 108 in high"],
            ["Allowable heat gain from this unit", "15 kW"]]
    return [[("h", f"RIGGING AND ACCESS NOTES {SYN}"), ("p", "Rev 1"), ("table", rows, [260, 220])]]


def tpl_meridian(d: dict[str, Any], scanned_weights: bool) -> list[list[tuple]]:
    """Plain specification sheet; the weights page is a scan unless a readable copy is supplied."""
    p1: list[tuple] = [("h", f"SPECIFICATION SHEET - LIQUID-FILLED TRANSFORMER {SYN}"),
                       ("p", f"Manufacturer: {d['mfr']}"), ("p", f"Model designation: {d['model']}"), ("p", f"Revision: {d['rev']}"),
                       ("p", f"Rated capacity: {d['kva']:,} kVA"),
                       ("p", "Rated voltage HV/LV: 13.8 kV / 480Y/277 V")]
    if "z_pct" in d:
        p1.append(("p", f"Impedance: {d['z_pct']:.2f} % at rated kVA"))
    else:
        p1.append(("p", "Impedance: per IEEE C57.12.00 standard values; guaranteed value on request"))
    p1.append(("p", "Vector group Dyn11"))
    L, W, H = d["dims"]
    p2: list[tuple] = [("h", "Dimensions and delivery"),
                       ("p", f"Dimensions: {L:,} mm (L) x {W:,} mm (W) x {H:,} mm (H)"),
                       ("p", f"Delivery: ex-works {d['lead_max']:g} weeks" + (" from PO" if d.get("start") == "order" else ""))]
    p3: list[tuple] = [("h", "Weights and losses"),
                       ("p", f"Shipping weight, heaviest section: {d['sections'][0][1]:,} kg"),
                       ("p", f"Total weight (filled): {d['total_kg']:,} kg"),
                       ("p", f"Total losses: {d['heat_kw']:.1f} kW")]
    return [p1, p2, p3]


def tpl_meridian_logistics(d: dict[str, Any]) -> list[list[tuple]]:
    rows = [["Site item", "Limit"],
            ["Freight lift (goods) maximum load", "4,500 kg"],
            ["Floor capacity", "3,000 kg per square metre"],
            ["Plant room door, W x H", "2,100 mm x 2,400 mm"],
            ["Cooling available for equipment heat", "18 kW"],
            ["Ceiling height clear", "3,200 mm"]]
    return [[("h", f"PLANT ROOM ACCESS LIMITS {SYN}"), ("p", "Rev 2"), ("table", rows, [260, 220])]]
