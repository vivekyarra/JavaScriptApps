"""Rules-based field extraction with verified quotes.

The extractor reads text-based documents and returns, for every supported field, one of:
documented / not_stated / could_not_read / conflicting - each documented value carries the page
and the verbatim line it came from. No value is ever invented: if a line does not state a value
with a clear unit, the field stays not_stated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from . import units as U
from .ingest import ParsedDocument
from .schemas import Evidence, FieldValue

NUM = U.NUM

EQUIPMENT_FIELDS = [
    "manufacturer",
    "model",
    "rated_kva",
    "primary_voltage_v",
    "secondary_voltage_v",
    "impedance_pct",
    "xd_subtransient_pct",
    "winding_config",
    "dimensions_mm",
    "heaviest_transport_weight_kg",
    "shipping_total_weight_kg",
    "total_weight_kg",
    "heat_loss_kw",
    "lead_time_weeks",
    "lead_time_start",
]
CONSTRAINT_FIELDS = [
    "elevator_capacity_kg",
    "slab_limit_kg_m2",
    "door_width_mm",
    "door_height_mm",
    "ceiling_clearance_mm",
    "cooling_capacity_kw",
]
FIELD_LABELS = {
    "manufacturer": "Manufacturer",
    "model": "Model / type",
    "rated_kva": "Rated power (kVA)",
    "primary_voltage_v": "Primary voltage (V)",
    "secondary_voltage_v": "Secondary voltage (V)",
    "impedance_pct": "Impedance (%Z)",
    "xd_subtransient_pct": "Subtransient reactance Xd'' (%)",
    "winding_config": "Winding configuration",
    "dimensions_mm": "Overall dimensions (mm)",
    "heaviest_transport_weight_kg": "Heaviest transported section (kg)",
    "shipping_total_weight_kg": "Total shipping weight (kg)",
    "total_weight_kg": "Total weight (kg)",
    "heat_loss_kw": "Heat loss / rejection (kW)",
    "lead_time_weeks": "Quoted lead time (weeks)",
    "lead_time_start": "Lead-time start condition",
    "elevator_capacity_kg": "Freight elevator capacity (kg)",
    "slab_limit_kg_m2": "Floor loading limit (kg/m²)",
    "door_width_mm": "Door clear width (mm)",
    "door_height_mm": "Door clear height (mm)",
    "ceiling_clearance_mm": "Ceiling / overhead clearance (mm)",
    "cooling_capacity_kw": "Room cooling capacity (kW)",
}
FIELD_UNITS = {
    "rated_kva": "kVA",
    "primary_voltage_v": "V",
    "secondary_voltage_v": "V",
    "impedance_pct": "%",
    "xd_subtransient_pct": "%",
    "dimensions_mm": "mm",
    "heaviest_transport_weight_kg": "kg",
    "shipping_total_weight_kg": "kg",
    "total_weight_kg": "kg",
    "heat_loss_kw": "kW",
    "lead_time_weeks": "weeks",
    "elevator_capacity_kg": "kg",
    "slab_limit_kg_m2": "kg/m²",
    "door_width_mm": "mm",
    "door_height_mm": "mm",
    "ceiling_clearance_mm": "mm",
    "cooling_capacity_kw": "kW",
}

# --------------------------------------------------------------------------- helpers
_TOL_RE = re.compile(r"(?:±|\+/-|\+-|plus or minus)\s*\d+(?:\.\d+)?\s*%?", re.I)
_TEMP_RE = re.compile(
    r"(?:\b(?:at|@)\s*\d{2,3}\s*°?\s*(?:deg\w*\.?\s*)?[CF]\b"
    r"|\(\s*\d{2,3}\s*°?\s*(?:deg\w*\.?\s*)?[CF]\s*\)"
    r"|\bref(?:erence|\.)?\s*(?:temp(?:erature|\.)?)?\s*\d{2,3}\s*°?\s*[CF]\b"
    r"|@\s*\d{2,3}\s*°?\s*[CF]\b)",
    re.I,
)
_STD_RE = re.compile(
    r"\b(?:IEEE|IEC|ANSI|NEMA|NFPA|UL|CSA|ISO|NEC|EN)\b[\s\-]*(?:Std\.?\s*)?[A-Z]?\d[\d.\-/]*(?:\.\d+)*",
    re.I,
)
_QUOTE_FIX = str.maketrans({"“": '"', "”": '"', "″": '"', "’": "'", "‘": "'", "′": "'"})


def clean_line(line: str) -> str:
    s = line.translate(_QUOTE_FIX)
    s = _TOL_RE.sub(" ", s)
    s = _TEMP_RE.sub(" ", s)
    s = _STD_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_quote(page_text: str, quote: str) -> bool:
    return norm_ws(quote).lower() in norm_ws(page_text).lower()


@dataclass
class Cand:
    value: Any
    page: int
    quote: str
    unit: Optional[str] = None
    explicit_unit: bool = True
    qualifier: Optional[str] = None
    detail: Any = None
    note: Optional[str] = None
    kind: str = ""
    extra_quotes: list[tuple[int, str]] = field(default_factory=list)


def _qualifier(line: str) -> Optional[str]:
    low = line.lower()
    if re.search(r"\b(not less than|at least|minimum|min\.?|no less than)\b|≥|>=", low):
        return "min"
    if re.search(r"\b(not (?:more|greater|exceeding)|maximum|max\.?|at most|no more than|up to)\b|≤|<=", low):
        return "max"
    return None


def _lines(doc: ParsedDocument) -> Iterable[tuple[int, str]]:
    for p in doc.pages:
        if p.status != "ok":
            continue
        for raw in p.text.splitlines():
            line = raw.strip()
            if line:
                yield p.number, line


# --------------------------------------------------------------------------- field scanners
_KVA_RE = re.compile(rf"({NUM})((?:\s*/\s*(?:{NUM}))*)\s*(kVA|MVA)\b", re.I)
_KVA_LABEL_FIRST = re.compile(rf"\b(kva|mva)\b(?:\s*rating)?\s*[:=]\s*({NUM})", re.I)
_KVA_EXCL = re.compile(r"\b(short[- ]circuit|fault|aic|sccr|withstand|no[- ]load|loss(?:es)?|inrush|bil)\b", re.I)
_FORCED = re.compile(r"\b(ONAF|KNAF|OFAF|ODAF|FA|AF|forced|fan[- ]cooled|fans?)\b", re.I)
_SELF = re.compile(r"\b(ONAN|KNAN|OA|AA|self[- ]cooled|natural)\b", re.I)


def scan_rated_kva(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = clean_line(line)
        if _KVA_EXCL.search(s):
            continue
        m = _KVA_RE.search(s)
        mv: Optional[float] = None
        unit_txt = None
        if m:
            first = U.parse_number(m.group(1))
            unit_txt = m.group(3)
            if first is not None:
                mv = U.kva_from(first, unit_txt)
        else:
            m2 = _KVA_LABEL_FIRST.search(s)
            if m2:
                first = U.parse_number(m2.group(2))
                if first is not None:
                    mv = U.kva_from(first, m2.group(1))
        if mv is None:
            continue
        if _FORCED.search(s) and not _SELF.search(s):
            continue  # forced-cooled rating is not the base rating
        out.append(Cand(mv, page, line, "kVA", qualifier=_qualifier(line)))
    return out


_VOLT_NUM = rf"({NUM})\s*(?:[YyΔ](?:\s*/\s*{NUM})?)?\s*(kV|V)\b"
_RATIO_RE = re.compile(
    rf"({NUM})\s*(kV|V)?\s*(?:/|-|–|—|to|:)\s*({NUM})\s*[YyΔ]?(?:\s*/\s*{NUM})?\s*(kV|V)\b",
    re.I,
)
_PRI_LABEL = re.compile(r"\b(primary|hv|h\.v\.|high[- ]?voltage|input)\b", re.I)
_SEC_LABEL = re.compile(r"\b(secondary|lv|l\.v\.|low[- ]?voltage|output)\b", re.I)
_VOLT_EXCL = re.compile(r"\b(bil|insulation|withstand|impulse|test|tap|taps)\b", re.I)


def scan_voltages(doc: ParsedDocument) -> tuple[list[Cand], list[Cand]]:
    pri: list[Cand] = []
    sec: list[Cand] = []
    for page, line in _lines(doc):
        s = clean_line(line)
        if _VOLT_EXCL.search(s):
            continue
        low = s.lower()
        if not re.search(r"\b(volt|voltage|ratio|primary|secondary|hv|lv|kv|v)\b", low):
            continue
        labels = sorted(
            [(m.start(), "p") for m in _PRI_LABEL.finditer(s)] + [(m.start(), "s") for m in _SEC_LABEL.finditer(s)]
        )
        matched_labelled = False
        for i, (pos, kind) in enumerate(labels):
            end = labels[i + 1][0] if i + 1 < len(labels) else len(s)
            seg = s[pos:end]
            mm = re.search(_VOLT_NUM, seg, re.I)
            if mm:
                n = U.parse_number(mm.group(1))
                v = U.volts_from(n, mm.group(2)) if n is not None else None
                if v is not None and v > 0:
                    (pri if kind == "p" else sec).append(Cand(v, page, line, "V"))
                    matched_labelled = True
        if matched_labelled:
            continue
        m = _RATIO_RE.search(s)
        if m:
            a = U.parse_number(m.group(1))
            b = U.parse_number(m.group(3))
            ua = m.group(2) or m.group(4)
            ub = m.group(4)
            if a is None or b is None:
                continue
            va, vb = U.volts_from(a, ua), U.volts_from(b, ub)
            if va is None or vb is None:
                continue
            if m.group(2) is None and vb > 0 and abs(va / vb - 1.732) < 0.02:
                continue  # 480/277 V is line-to-line / line-to-neutral, not a voltage ratio
            if va > vb:
                pri.append(Cand(va, page, line, "V"))
                sec.append(Cand(vb, page, line, "V"))
    return pri, sec


_IMP_LABEL = re.compile(r"(%\s*z\b|\bz\s*\(\s*%\s*\)|\bpercent(?:age)?\s+impedance|\bimpedance\b|\bimp\.)", re.I)
_IMP_EXCL = re.compile(r"zero[- ]sequence|\bz0\b|\bx0\b|\br0\b|\bnegative[- ]sequence", re.I)
_TIER1 = re.compile(rf"[^\d\n]{{0,40}}?({NUM})\s*(%|percent|pu|p\.u\.)", re.I)
_TIER2 = re.compile(rf"[\s:=\-–—.]*({NUM})\b(?!\s*(?:kv|v\b|kva|ohm|Ω|mm|kg))", re.I)


_TOL_VALUE = re.compile(r"(?:±|\+/-|\+-|plus or minus)\s*(\d+(?:\.\d+)?)\s*%?", re.I)


def scan_impedance(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        if _IMP_EXCL.search(line):
            continue
        tol_m = _TOL_VALUE.search(line)
        tol = float(tol_m.group(1)) if tol_m else None
        s = clean_line(line)
        for lm in _IMP_LABEL.finditer(s):
            rest = s[lm.end():]
            m1 = _TIER1.match(rest)
            if m1:
                n = U.parse_number(m1.group(1))
                unit = m1.group(2).lower()
                if n is None:
                    continue
                if unit in {"pu", "p.u."}:
                    out.append(Cand(n * 100.0, page, line, "%", qualifier=_qualifier(line), note="stated in per-unit; converted to %", detail={"tolerance_pct": tol}))
                else:
                    out.append(Cand(n, page, line, "%", qualifier=_qualifier(line), detail={"tolerance_pct": tol}))
                break
            m2 = _TIER2.match(rest)
            if m2:
                n = U.parse_number(m2.group(1))
                if n is None:
                    continue
                if 0 < n < 1:
                    out.append(Cand(n * 100.0, page, line, "%", explicit_unit=False, qualifier=_qualifier(line),
                                    note="no unit stated; value below 1 read as per-unit", detail={"tolerance_pct": tol}))
                    break
                if 1 <= n <= 30:
                    out.append(Cand(n, page, line, "%", explicit_unit=False, qualifier=_qualifier(line),
                                    note="no unit stated; read as percent", detail={"tolerance_pct": tol}))
                    break
    return out


_XD_RE = re.compile(
    r"(sub-?transient\s+reactance|x\s*\"\s*d\b|x\s*d\s*\"|x\s*d\s*'{2}|x\s*'{2}\s*d\b|\bxd\"|\bx\"d)",
    re.I,
)


def scan_xd(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = clean_line(line)
        s = s.replace("''", '"')
        m = _XD_RE.search(s)
        if not m:
            continue
        rest = s[m.end():]
        mm = re.search(rf"[^\d\n]{{0,30}}?({NUM})\s*(%|pu|p\.u\.)?", rest, re.I)
        if not mm:
            continue
        n = U.parse_number(mm.group(1))
        if n is None:
            continue
        unit = (mm.group(2) or "").lower()
        if unit in {"pu", "p.u."} or (not unit and n < 1):
            out.append(Cand(n * 100.0, page, line, "%", explicit_unit=bool(unit), note="per-unit converted to %"))
        else:
            out.append(Cand(n, page, line, "%", explicit_unit=bool(unit)))
    return out


_WIND_LABEL = re.compile(r"(vector\s+group|winding\s+(?:connection|configuration|arrangement)s?|connections?|configuration|phase\s+displacement)", re.I)
_IEC_GROUP = re.compile(r"\b(YNyn\d{0,2}|Ynyn\d{0,2}|YNd\d{0,2}|Ynd\d{0,2}|Dyn\d{0,2}|Dy\d{1,2}|Dd\d{0,2}|Yd\d{0,2}|Yyn\d{0,2}|Yy\d{0,2})\b")
_WORD_FAMILIES = [
    (re.compile(r"\bdelta[\s\-–/]*(?:solidly\s+|resistance\s+)?(?:grounded\s+)?(?:wye|star|y)\b", re.I), "delta-wye"),
    (re.compile(r"\bdelta[\s\-–/]*delta\b", re.I), "delta-delta"),
    (re.compile(r"\b(?:wye|star|y)[\s\-–/]*(?:grounded\s+)?delta\b", re.I), "wye-delta"),
    (re.compile(r"\b(?:wye|star|y)[\s\-–/]*(?:grounded\s+)?(?:wye|star|y)\b", re.I), "wye-wye"),
]


def _iec_family(token: str) -> Optional[str]:
    t = token.lower()
    if t.startswith("dd"):
        return "delta-delta"
    if t.startswith("dy"):
        return "delta-wye"
    if re.match(r"yn?d", t):
        return "wye-delta"
    if re.match(r"yn?yn?", t):
        return "wye-wye"
    return None


def scan_winding(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    pri_conn: Optional[tuple[int, str, str]] = None
    sec_conn: Optional[tuple[int, str, str]] = None
    for page, line in _lines(doc):
        m = _WIND_LABEL.search(line)
        rest = line[m.end():] if m else ""
        found = False
        if m:
            g = _IEC_GROUP.search(rest)
            if g:
                fam = _iec_family(g.group(1))
                if fam:
                    out.append(Cand(fam, page, line, None, detail={"raw": g.group(1)}))
                    found = True
            if not found:
                for rx, fam in _WORD_FAMILIES:
                    if rx.search(rest):
                        out.append(Cand(fam, page, line, None, detail={"raw": norm_ws(rest)[:40]}))
                        found = True
                        break
        if found:
            continue
        pm = re.search(r"\bprimary\b[^\n]{0,40}?\b(delta|wye|star)\b", line, re.I)
        sm = re.search(r"\bsecondary\b[^\n]{0,40}?\b(delta|wye|star)\b", line, re.I)
        if pm and not pri_conn:
            pri_conn = (page, line, pm.group(1).lower())
        if sm and not sec_conn:
            sec_conn = (page, line, sm.group(1).lower())
    if not out and pri_conn and sec_conn:
        norm = {"star": "wye", "wye": "wye", "delta": "delta"}
        fam = f"{norm[pri_conn[2]]}-{norm[sec_conn[2]]}"
        c = Cand(fam, pri_conn[0], pri_conn[1], None, detail={"raw": f"primary {pri_conn[2]}, secondary {sec_conn[2]}"})
        c.extra_quotes.append((sec_conn[0], sec_conn[1]))
        out.append(c)
    return out


_UNIT_RE = r"(mm|cm|m|in|inches|inch|\")"
_TRIPLE = re.compile(
    rf"({NUM})\s*{_UNIT_RE}?\s*[x×X*]\s*({NUM})\s*{_UNIT_RE}?\s*[x×X*]\s*({NUM})\s*{_UNIT_RE}?(?![\w/])",
)
_ORDER = re.compile(r"\b([LWDH])\s*[x×X*]\s*([LWDH])\s*[x×X*]\s*([LWDH])\b")
_ORDER_WORDS = re.compile(r"\b(length|width|depth|height)\s*[x×X*]\s*(length|width|depth|height)\s*[x×X*]\s*(length|width|depth|height)\b", re.I)
_DIM_LABEL = re.compile(r"(dimension|footprint|overall\s+size|\bsize\b|\bL\s*[x×]\s*W|\bW\s*[x×]\s*D)", re.I)
_SINGLE_DIM = re.compile(rf"^\s*(?:overall\s+)?(length|width|depth|height)\b[^\d\n]{{0,25}}?({NUM})\s*{_UNIT_RE}", re.I)
_DIM_KEY = {"l": "length", "w": "width", "d": "length", "h": "height", "length": "length", "width": "width", "depth": "length", "height": "height"}


def scan_dimensions(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    singles: dict[int, dict[str, tuple[float, str]]] = {}
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        if _DIM_LABEL.search(s) or _TRIPLE.search(s):
            if re.search(r"\b(door|opening|corridor|elevator|room|clearance)\b", s, re.I):
                continue
            m = _TRIPLE.search(s)
            if m and _DIM_LABEL.search(s):
                unit = next((g for g in (m.group(2), m.group(4), m.group(6)) if g), None)
                if unit is None:
                    um = re.search(r"\b(mm|cm|in|inches|inch)\b|\(\s*(m)\s*\)", s, re.I)
                    unit = (um.group(1) or um.group(2)) if um else None
                if unit is None:
                    continue
                vals = []
                for g in (m.group(1), m.group(3), m.group(5)):
                    n = U.parse_number(g)
                    mm = U.length_to_mm(n, unit) if n is not None else None
                    vals.append(mm)
                if None in vals:
                    continue
                keys = None
                om = _ORDER.search(s)
                if om:
                    keys = [_DIM_KEY[x.lower()] for x in om.groups()]
                else:
                    ow = _ORDER_WORDS.search(s)
                    if ow:
                        keys = [_DIM_KEY[x.lower()] for x in ow.groups()]
                if keys and len(set(keys)) == 3:
                    out.append(Cand(dict(zip(keys, vals)), page, line, "mm", detail={"ordered": True}))
                else:
                    out.append(Cand({"unordered": sorted(vals)}, page, line, "mm", detail={"ordered": False}))
                continue
        sm = _SINGLE_DIM.match(s)
        if sm:
            n = U.parse_number(sm.group(2))
            mm = U.length_to_mm(n, sm.group(3)) if n is not None else None
            if mm is not None:
                key = _DIM_KEY[sm.group(1).lower()]
                singles.setdefault(page, {}).setdefault(key, (mm, line))
    if not out:
        for page, d in singles.items():
            if {"length", "width", "height"} <= set(d):
                lines = [d[k][1] for k in ("length", "width", "height")]
                c = Cand({k: d[k][0] for k in ("length", "width", "height")}, page, lines[0], "mm", detail={"ordered": True})
                c.extra_quotes = [(page, x) for x in lines[1:]]
                out.append(c)
    return out


_W_RE = re.compile(rf"({NUM})\s*(kgs?|tonnes?|metric tons?|t|lbs?\.?|pounds|kips?)(?![/\w²])", re.I)
_W_AMBIG = re.compile(rf"({NUM})\s*(tons?)\b", re.I)
_HEAVIEST = re.compile(r"\b(heaviest|largest|maximum|max\.?)\b", re.I)
_SECTION_WORDS = re.compile(r"\b(section|piece|split|segment|lift|lifting|shipping group|shipping unit)\b", re.I)
_SHIP_WORDS = re.compile(r"\b(shipping|shipped|shipment|transport(?:ation|ed)?)\b", re.I)
_COMPONENT_WORDS = re.compile(r"\b(core|coil|tank|radiator|conservator|bushing|skid|assembly|cabinet|enclosure|module|cubicle|vessel|crate|housing)\b", re.I)
_TOTAL_WORDS = re.compile(r"\b(total|gross|operating|in[- ]service|complete|installed|filled)\b", re.I)
_OIL = re.compile(r"\b(oil|coolant|fluid|liquid)\b", re.I)


def scan_weights(doc: ParsedDocument) -> dict[str, list[Cand]]:
    res: dict[str, list[Cand]] = {"heaviest": [], "section": [], "ship_total": [], "total": []}
    ambiguous_notes: list[tuple[int, str]] = []
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        m = _W_RE.search(s)
        if not m:
            if _W_AMBIG.search(s) and re.search(r"\b(weight|mass|section|piece|lift|heaviest)\b", s, re.I):
                ambiguous_notes.append((page, line))
            continue
        n = U.parse_number(m.group(1))
        kg = U.weight_to_kg(n, m.group(2)) if n is not None else None
        if kg is None:
            continue
        low = s.lower()
        has_weight_word = re.search(r"\b(weight|mass|wt\.?)\b", low) is not None
        is_heaviest = bool(_HEAVIEST.search(s)) and bool(_SECTION_WORDS.search(s) or _SHIP_WORDS.search(s) or re.search(r"\b(unit|package|crate)\b", low))
        is_section = bool(_SECTION_WORDS.search(s)) or (bool(_COMPONENT_WORDS.search(s)) and bool(_SHIP_WORDS.search(s)))
        is_total = bool(_TOTAL_WORDS.search(s)) and has_weight_word
        is_ship_total = bool(_SHIP_WORDS.search(s)) and has_weight_word
        if _OIL.search(s) and not (is_section or is_heaviest or is_total):
            continue
        if is_heaviest:
            res["heaviest"].append(Cand(kg, page, line, "kg"))
        elif is_section and (_SHIP_WORDS.search(s) or has_weight_word or re.search(r"\b(section|piece)\s*\w{0,3}\b", low)) and not is_total:
            res["section"].append(Cand(kg, page, line, "kg", detail={"label": norm_ws(s[: m.start()]).strip(" :-–—|")}))
        elif is_total and not is_ship_total:
            res["total"].append(Cand(kg, page, line, "kg"))
        elif is_ship_total:
            res["ship_total"].append(Cand(kg, page, line, "kg"))
        elif is_total:
            res["total"].append(Cand(kg, page, line, "kg"))
        elif has_weight_word and re.match(r"^\s*(?:approx\.?\s*)?(?:unit\s+)?(?:weight|mass)\b", low):
            res["total"].append(Cand(kg, page, line, "kg", explicit_unit=True,
                                     note="unqualified 'weight' read as total weight"))
    res["_ambiguous"] = [Cand(None, p, q, None) for p, q in ambiguous_notes]  # type: ignore[assignment]
    return res


_HEAT_TOTAL = re.compile(r"(total\s+(?:losses|loss|heat)|heat\s+(?:loss|rejection|dissipation)|losses?\s*,?\s*total)", re.I)
_NOLOAD = re.compile(r"\bno[- ]load\s+loss(?:es)?\b", re.I)
_LOADLOSS = re.compile(r"(?<!no[- ])(?<!no)\bload\s+loss(?:es)?\b", re.I)
_P_RE = re.compile(rf"({NUM})\s*(kW|W|MW|BTU/h|BTU/hr|BTUH)\b", re.I)


def scan_heat(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    nl: Optional[Cand] = None
    ll: Optional[Cand] = None
    for page, line in _lines(doc):
        s = clean_line(line)
        m = _P_RE.search(s)
        if not m:
            continue
        n = U.parse_number(m.group(1))
        kw = U.power_to_kw(n, m.group(2)) if n is not None else None
        if kw is None:
            continue
        if _NOLOAD.search(s) and not _HEAT_TOTAL.search(s):
            nl = nl or Cand(kw, page, line, "kW")
        elif _LOADLOSS.search(s) and not _HEAT_TOTAL.search(s):
            ll = ll or Cand(kw, page, line, "kW")
        elif _HEAT_TOTAL.search(s):
            out.append(Cand(kw, page, line, "kW"))
    if not out and nl and ll:
        c = Cand(nl.value + ll.value, nl.page, nl.quote, "kW", detail={"sum_of": ["no-load loss", "load loss"]},
                 note="sum of no-load loss and load loss")
        c.extra_quotes.append((ll.page, ll.quote))
        out.append(c)
    return out


_LT_LABEL = re.compile(
    r"(lead\s*time|delivery(?:\s+time)?|ex[- ]works|ship(?:ment|ping)?\s+(?:time|lead)|production\s+time|manufactur(?:e|ing)\s+(?:time|lead)|delivery\s+period)",
    re.I,
)
_LT_VAL = re.compile(rf"({NUM})\s*(?:(?:-|–|—|to)\s*({NUM})\s*)?(weeks?|wks?|wk|days?|months?|mos?)\b", re.I)
_START_ORDER = re.compile(
    r"\b(aro|(?:after|from|upon)\s+receipt\s+of\s+(?:(?:purchase\s+)?order|po)|from\s+(?:po|p\.o\.|purchase\s+order|order)(?:\s+(?:placement|release|receipt))?|after\s+(?:po|order)\b|from\s+order\s+release|after\s+order\s+(?:placement|release|confirmation))",
    re.I,
)
_START_APPR = re.compile(
    r"\b(ara|after\s+(?:receipt\s+of\s+)?(?:approved|approval)|from\s+(?:approved|approval)|after\s+(?:drawing|submittal)\s+approval|approved\s+(?:drawings?|submittals?)|after\s+release\s+for\s+(?:manufacture|production))",
    re.I,
)


def scan_lead_time(doc: ParsedDocument) -> tuple[list[Cand], list[Cand]]:
    lts: list[Cand] = []
    starts: list[Cand] = []
    lines = list(_lines(doc))
    for idx, (page, line) in enumerate(lines):
        s = line.translate(_QUOTE_FIX)
        lm = _LT_LABEL.search(s)
        if not lm:
            continue
        m = _LT_VAL.search(s[lm.end():]) or _LT_VAL.search(s)
        if not m:
            continue
        lo = U.parse_number(m.group(1))
        hi = U.parse_number(m.group(2)) if m.group(2) else lo
        if lo is None or hi is None:
            continue
        wlo, approx = U.time_to_weeks(lo, m.group(3))
        whi, _ = U.time_to_weeks(hi, m.group(3))
        if wlo is None or whi is None:
            continue
        lo_w, hi_w = min(wlo, whi), max(wlo, whi)
        note = "months converted at 52/12 weeks per month" if approx else None
        lts.append(Cand(hi_w, page, line, "weeks", explicit_unit=not approx, detail={"min": lo_w, "max": hi_w}, note=note))
        window = s
        nxt = lines[idx + 1][1] if idx + 1 < len(lines) and lines[idx + 1][0] == page else ""
        if _START_ORDER.search(window) or _START_APPR.search(window) or not (_START_ORDER.search(nxt) or _START_APPR.search(nxt)):
            ctx_line, ctx_page = line, page
        else:
            window = s + " " + nxt
            ctx_line, ctx_page = nxt, page
        if _START_ORDER.search(window):
            c = Cand("order", ctx_page, ctx_line, None)
            if ctx_line != line:
                c.extra_quotes.append((page, line))
            starts.append(c)
        elif _START_APPR.search(window):
            c = Cand("approval", ctx_page, ctx_line, None)
            if ctx_line != line:
                c.extra_quotes.append((page, line))
            starts.append(c)
    return lts, starts


def scan_identity(doc: ParsedDocument) -> tuple[list[Cand], list[Cand]]:
    mans: list[Cand] = []
    models: list[Cand] = []
    for page, line in _lines(doc):
        m = re.match(r"^\s*(?:manufacturer|supplier|vendor|make)\s*[:\-–]\s*(.{2,60})$", line, re.I)
        if m:
            mans.append(Cand(norm_ws(m.group(1)), page, line))
        m = re.match(r"^\s*(?:model(?:\s*(?:no\.?|number|designation))?|catalog(?:ue)?\s*(?:no\.?|number)|part\s*(?:no\.?|number)|product\s*code|type\s*designation)\s*[:#\-–]\s*([A-Za-z0-9][A-Za-z0-9\-_/\. ]{2,40})$", line, re.I)
        if m:
            models.append(Cand(norm_ws(m.group(1)), page, line))
    return mans, models


# --------------------------------------------------------------------------- constraint scanners
_ELEV = re.compile(r"\b(elevator|lift|hoist)\b", re.I)
_CAP = re.compile(r"\b(capacity|rated|rating|limit|load|max(?:imum)?)\b", re.I)
_FREIGHT = re.compile(r"\b(freight|service|goods|cargo|material)\b", re.I)


def scan_elevator(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        if not (_ELEV.search(s) and _CAP.search(s)) or re.search(r"\bcrane\b", s, re.I):
            continue
        m = _W_RE.search(s)
        if not m:
            continue
        n = U.parse_number(m.group(1))
        kg = U.weight_to_kg(n, m.group(2)) if n is not None else None
        if kg is not None:
            out.append(Cand(kg, page, line, "kg", detail={"freight": bool(_FREIGHT.search(s))}))
    freight = [c for c in out if c.detail and c.detail.get("freight")]
    return freight or out


_PRESS_RE = re.compile(rf"({NUM})\s*(kg/m2|kg/m²|kPa|kN/m2|kN/m²|psf|lbs?/ft2|lbs?/ft²|lbs?/sq\.? ?ft)", re.I)


def scan_slab(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        if not re.search(r"\b(floor|slab|loading|load)\b", s, re.I):
            continue
        m = _PRESS_RE.search(s)
        if not m:
            continue
        n = U.parse_number(m.group(1))
        v = U.pressure_to_kg_m2(n, m.group(2)) if n is not None else None
        if v is not None:
            out.append(Cand(v, page, line, "kg/m²"))
    return out


_DOOR = re.compile(r"\b(door|doorway|opening|entrance)\b", re.I)
_PAIR = re.compile(rf"({NUM})\s*{_UNIT_RE}?\s*[x×X*]\s*({NUM})\s*{_UNIT_RE}?(?![\w/])")


def scan_door(doc: ParsedDocument) -> tuple[list[Cand], list[Cand]]:
    widths: list[Cand] = []
    heights: list[Cand] = []
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        if not _DOOR.search(s):
            continue
        pm = _PAIR.search(s)
        if pm and re.search(r"\b(w\s*[x×]\s*h|width\s*[x×]\s*height)\b", s, re.I):
            unit = pm.group(2) or pm.group(4)
            if unit is None:
                um = re.search(r"\b(mm|cm|in|inches|m)\b", s, re.I)
                unit = um.group(1) if um else None
            if unit:
                a, b = U.parse_number(pm.group(1)), U.parse_number(pm.group(3))
                wa = U.length_to_mm(a, unit) if a is not None else None
                hb = U.length_to_mm(b, unit) if b is not None else None
                if wa is not None and hb is not None:
                    widths.append(Cand(wa, page, line, "mm"))
                    heights.append(Cand(hb, page, line, "mm"))
                    continue
        for key, bucket in (("width", widths), ("height", heights)):
            m = re.search(rf"\b(?:clear\s+)?{key}\b[^\d\n]{{0,25}}?({NUM})\s*{_UNIT_RE}", s, re.I)
            if m:
                n = U.parse_number(m.group(1))
                mm = U.length_to_mm(n, m.group(2)) if n is not None else None
                if mm is not None:
                    bucket.append(Cand(mm, page, line, "mm"))
    return widths, heights


def scan_ceiling(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = line.translate(_QUOTE_FIX)
        if not re.search(r"\b(ceiling|overhead|headroom|clear\s+height)\b", s, re.I):
            continue
        m = re.search(rf"({NUM})\s*{_UNIT_RE}", s)
        if m:
            n = U.parse_number(m.group(1))
            mm = U.length_to_mm(n, m.group(2)) if n is not None else None
            if mm is not None:
                out.append(Cand(mm, page, line, "mm"))
    return out


def scan_cooling(doc: ParsedDocument) -> list[Cand]:
    out: list[Cand] = []
    for page, line in _lines(doc):
        s = clean_line(line)
        if not re.search(r"\b(cooling|heat\s+(?:removal|rejection|load)|hvac|crah)\b", s, re.I):
            continue
        if not re.search(r"\b(capacity|limit|available|rated|max(?:imum)?)\b", s, re.I):
            continue
        m = _P_RE.search(s)
        if m:
            n = U.parse_number(m.group(1))
            kw = U.power_to_kw(n, m.group(2)) if n is not None else None
            if kw is not None:
                out.append(Cand(kw, page, line, "kW"))
    return out


# --------------------------------------------------------------------------- resolution
def _evidence(doc: ParsedDocument, page: int, quote: str) -> Evidence:
    text = next((p.text for p in doc.pages if p.number == page), "")
    return Evidence(
        document=doc.name,
        role=doc.role,
        revision=doc.effective_revision,
        sha256=doc.sha256,
        page=page,
        quote=quote,
        verified=verify_quote(text, quote),
    )


def _evidence_for(doc: ParsedDocument, cands: list[Cand]) -> list[Evidence]:
    seen: set[tuple[int, str]] = set()
    out: list[Evidence] = []
    for c in cands:
        for page, quote in [(c.page, c.quote), *c.extra_quotes]:
            if (page, quote) in seen:
                continue
            seen.add((page, quote))
            out.append(_evidence(doc, page, quote))
    return out


def _confidence(cands: list[Cand], doc: ParsedDocument, corroborated: bool) -> float:
    score = 0.6
    if all(c.explicit_unit for c in cands):
        score += 0.2
    else:
        score -= 0.2
    if corroborated:
        score += 0.1
    if any(c.note and "month" in c.note for c in cands):
        score -= 0.1
    if any(p.status != "ok" for p in doc.pages):
        score -= 0.1
    if any(c.note and "unqualified" in c.note for c in cands):
        score -= 0.15
    return max(0.05, min(0.95, round(score, 2)))


def _absent(field_name: str, doc: ParsedDocument, why_note: Optional[str] = None) -> FieldValue:
    bad = [p.number for p in doc.pages if p.status != "ok"]
    notes = [why_note] if why_note else []
    if bad:
        return FieldValue(
            field=field_name,
            status="could_not_read",
            unit=FIELD_UNITS.get(field_name),
            unreadable_pages=bad,
            confidence=0.0,
            notes=notes + [f"not found on readable pages; page(s) {bad} could not be read"],
        )
    return FieldValue(
        field=field_name,
        status="not_stated",
        unit=FIELD_UNITS.get(field_name),
        confidence=0.85,
        notes=notes + ["not found on any readable page"],
    )


def _resolve_numeric(field_name: str, doc: ParsedDocument, cands: list[Cand], key: Callable[[Cand], Any] = lambda c: c.value) -> FieldValue:
    if not cands:
        return _absent(field_name, doc)
    values = [key(c) for c in cands]
    base = values[0]
    agree = all(U.same_number(base, v, rel=2e-3) for v in values)
    if not agree:
        return FieldValue(
            field=field_name,
            status="conflicting",
            unit=FIELD_UNITS.get(field_name),
            detail={"candidates": [{"value": key(c), "page": c.page, "quote": c.quote} for c in cands]},
            evidence=_evidence_for(doc, cands),
            confidence=0.0,
            notes=["the document states different values for this field"],
        )
    notes = sorted({c.note for c in cands if c.note})
    qual = next((c.qualifier for c in cands if c.qualifier), None)
    bad = [p.number for p in doc.pages if p.status != "ok"]
    if bad:
        notes.append(f"page(s) {bad} could not be read; a contradicting value there would be missed")
    tol = next((c.detail.get("tolerance_pct") for c in cands if isinstance(c.detail, dict) and c.detail.get("tolerance_pct") is not None), None)
    return FieldValue(
        field=field_name,
        status="documented",
        value=base,
        unit=FIELD_UNITS.get(field_name),
        qualifier=qual,
        detail={"tolerance_pct": tol} if tol is not None else None,
        evidence=_evidence_for(doc, cands),
        confidence=_confidence(cands, doc, corroborated=len({(c.page, c.quote) for c in cands}) > 1),
        notes=notes,
        unreadable_pages=bad,
    )


def _resolve_string(field_name: str, doc: ParsedDocument, cands: list[Cand]) -> FieldValue:
    if not cands:
        return _absent(field_name, doc)
    vals = {str(c.value).lower() for c in cands}
    if len(vals) > 1:
        return FieldValue(
            field=field_name,
            status="conflicting",
            detail={"candidates": [{"value": c.value, "page": c.page, "quote": c.quote} for c in cands]},
            evidence=_evidence_for(doc, cands),
            notes=["the document states different values for this field"],
        )
    return FieldValue(
        field=field_name,
        status="documented",
        value=cands[0].value,
        detail=cands[0].detail,
        evidence=_evidence_for(doc, cands),
        confidence=_confidence(cands, doc, corroborated=len(cands) > 1),
    )


def _dim_values(c: Cand) -> list[float]:
    v = c.value
    return sorted(v["unordered"] if "unordered" in v else list(v.values()))


def _resolve_dims(doc: ParsedDocument, cands: list[Cand]) -> FieldValue:
    if not cands:
        return _absent("dimensions_mm", doc)
    first = cands[0]
    for c in cands[1:]:
        if any(not U.same_number(a, b, rel=5e-3) for a, b in zip(_dim_values(first), _dim_values(c))):
            return FieldValue(
                field="dimensions_mm",
                status="conflicting",
                unit="mm",
                detail={"candidates": [{"value": c2.value, "page": c2.page, "quote": c2.quote} for c2 in cands]},
                evidence=_evidence_for(doc, cands),
                notes=["the document states different overall dimensions"],
            )
    ordered = bool(first.detail and first.detail.get("ordered"))
    return FieldValue(
        field="dimensions_mm",
        status="documented",
        value=first.value,
        unit="mm",
        detail={"ordered": ordered, "sorted_mm": _dim_values(first)},
        evidence=_evidence_for(doc, cands),
        confidence=_confidence(cands, doc, corroborated=len(cands) > 1),
        notes=[] if ordered else ["dimension order (length / width / height) is not labelled"],
    )


def _resolve_weights(doc: ParsedDocument, w: dict[str, list[Cand]]) -> dict[str, FieldValue]:
    out: dict[str, FieldValue] = {}
    ambiguous = w.pop("_ambiguous", [])  # type: ignore[arg-type]
    heaviest, sections = w["heaviest"], w["section"]
    if heaviest or sections:
        allc = heaviest + sections
        mx = max(c.value for c in allc)
        explicit = max((c.value for c in heaviest), default=None)
        if explicit is not None and sections and not U.same_number(explicit, mx, rel=2e-3) and explicit < mx:
            out["heaviest_transport_weight_kg"] = FieldValue(
                field="heaviest_transport_weight_kg",
                status="conflicting",
                unit="kg",
                detail={"candidates": [{"value": c.value, "page": c.page, "quote": c.quote} for c in allc]},
                evidence=_evidence_for(doc, allc),
                notes=["the stated heaviest piece is lighter than a listed section"],
            )
        else:
            out["heaviest_transport_weight_kg"] = FieldValue(
                field="heaviest_transport_weight_kg",
                status="documented",
                value=mx,
                unit="kg",
                detail={
                    "sections": [
                        {"label": (c.detail or {}).get("label"), "kg": c.value, "page": c.page, "quote": c.quote}
                        for c in allc
                    ]
                },
                evidence=_evidence_for(doc, allc),
                confidence=_confidence(allc, doc, corroborated=len(allc) > 1),
                notes=[] if len(allc) == 1 else ["largest of the listed shipping sections"],
                unreadable_pages=[p.number for p in doc.pages if p.status != "ok"],
            )
    else:
        out["heaviest_transport_weight_kg"] = _absent("heaviest_transport_weight_kg", doc)
    out["shipping_total_weight_kg"] = _resolve_numeric("shipping_total_weight_kg", doc, w["ship_total"])
    out["total_weight_kg"] = _resolve_numeric("total_weight_kg", doc, w["total"])
    if ambiguous:
        for f in ("heaviest_transport_weight_kg", "shipping_total_weight_kg", "total_weight_kg"):
            fv = out[f]
            if fv.status in {"not_stated", "could_not_read"}:
                fv.notes.append(
                    "a weight in 'ton(s)' was found but the unit is ambiguous (short ton vs tonne); request kg or lb"
                )
                fv.evidence = [_evidence(doc, c.page, c.quote) for c in ambiguous[:2]]
    return out


def _resolve_heat(doc: ParsedDocument, cands: list[Cand]) -> FieldValue:
    return _resolve_numeric("heat_loss_kw", doc, cands)


def _resolve_lead(doc: ParsedDocument, lts: list[Cand], starts: list[Cand]) -> tuple[FieldValue, FieldValue]:
    if not lts:
        return _absent("lead_time_weeks", doc), _absent("lead_time_start", doc)
    fv = _resolve_numeric("lead_time_weeks", doc, lts)
    if fv.status == "documented":
        fv.detail = lts[0].detail
    if not starts:
        sv = FieldValue(
            field="lead_time_start",
            status="not_stated",
            confidence=0.85,
            notes=["the lead time does not say whether it counts from order placement or from approved drawings"],
        )
    else:
        kinds = {c.value for c in starts}
        if len(kinds) > 1:
            sv = FieldValue(
                field="lead_time_start",
                status="conflicting",
                evidence=_evidence_for(doc, starts),
                notes=["the document gives two different start conditions"],
            )
        else:
            sv = FieldValue(
                field="lead_time_start",
                status="documented",
                value=starts[0].value,
                evidence=_evidence_for(doc, starts),
                confidence=0.85,
            )
    return fv, sv


def extract_equipment(doc: ParsedDocument) -> dict[str, FieldValue]:
    out: dict[str, FieldValue] = {}
    mans, models = scan_identity(doc)
    out["manufacturer"] = _resolve_string("manufacturer", doc, mans)
    out["model"] = _resolve_string("model", doc, models)
    out["rated_kva"] = _resolve_numeric("rated_kva", doc, scan_rated_kva(doc))
    pri, sec = scan_voltages(doc)
    out["primary_voltage_v"] = _resolve_numeric("primary_voltage_v", doc, pri)
    out["secondary_voltage_v"] = _resolve_numeric("secondary_voltage_v", doc, sec)
    out["impedance_pct"] = _resolve_numeric("impedance_pct", doc, scan_impedance(doc))
    out["xd_subtransient_pct"] = _resolve_numeric("xd_subtransient_pct", doc, scan_xd(doc))
    out["winding_config"] = _resolve_string("winding_config", doc, scan_winding(doc))
    out["dimensions_mm"] = _resolve_dims(doc, scan_dimensions(doc))
    out.update(_resolve_weights(doc, scan_weights(doc)))
    out["heat_loss_kw"] = _resolve_heat(doc, scan_heat(doc))
    lts, starts = scan_lead_time(doc)
    out["lead_time_weeks"], out["lead_time_start"] = _resolve_lead(doc, lts, starts)
    return out


def extract_constraints(doc: ParsedDocument) -> dict[str, FieldValue]:
    out: dict[str, FieldValue] = {}
    out["elevator_capacity_kg"] = _resolve_numeric("elevator_capacity_kg", doc, scan_elevator(doc))
    out["slab_limit_kg_m2"] = _resolve_numeric("slab_limit_kg_m2", doc, scan_slab(doc))
    widths, heights = scan_door(doc)
    out["door_width_mm"] = _resolve_numeric("door_width_mm", doc, widths)
    out["door_height_mm"] = _resolve_numeric("door_height_mm", doc, heights)
    out["ceiling_clearance_mm"] = _resolve_numeric("ceiling_clearance_mm", doc, scan_ceiling(doc))
    out["cooling_capacity_kw"] = _resolve_numeric("cooling_capacity_kw", doc, scan_cooling(doc))
    return out


def extract_document(doc: ParsedDocument) -> dict[str, FieldValue]:
    if doc.role == "logistics":
        return extract_constraints(doc)
    if doc.role in {"spec", "original", "alternate"}:
        return extract_equipment(doc)
    return {}


def detect_equipment_type(docs: list[ParsedDocument]) -> str:
    text = " ".join(p.text for d in docs for p in d.pages if p.status == "ok").lower()
    t = len(re.findall(r"\btransformer", text))
    g = len(re.findall(r"\b(generator|genset|generating set|alternator)", text))
    if t == 0 and g == 0:
        return "unknown"
    return "transformer" if t >= g else "generator"
