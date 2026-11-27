"""Multi-model catalogue tables: use the offered model's column, never the first number on the row.

A datasheet that lists several models in columns is the classic way to read the wrong value. This module
finds such tables in the page text. If the offered model matches a column, that column's cells become
ordinary single-model lines (with the original table row kept as the citation). If the offered model is
not known or not in the table, the table's rows are withheld and the fields they would have supplied are
reported as conflicting instead of guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .ingest import ParsedDocument, Page

_CELL = re.compile(r"^\d[\w,./\-]*$")
_UNIT_LABEL = re.compile(r"^(.*?)\s*\(\s*(kVA|MVA|kV|V|%|kW|W|kg|lb|lbs|mm|cm|m|in|A|kA|Hz|weeks|days|t)\s*\)\s*:?$", re.I)
_TRAIL_UNIT = re.compile(r"^[A-Za-z%/]{1,5}$")


@dataclass
class MultiTable:
    page: int
    header_line: str
    models: list[str]
    rows: list[tuple[str, list[str], str, str]]  # label, cells, raw line, trailing unit
    model_raws: Optional[list[str]] = None  # models-in-rows tables: the raw row of each model
    lines: Optional[list[str]] = None  # every raw line the table occupies


def _norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def _is_header_token(tok: str) -> bool:
    return bool(re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok) and len(tok) >= 3) or bool(re.fullmatch(r"\d{3,5}", tok))


def _suffix(tokens: list[str], pred) -> tuple[list[str], list[str]]:
    k = 0
    while k < len(tokens) and pred(tokens[-1 - k]):
        k += 1
    return tokens[: len(tokens) - k], tokens[len(tokens) - k:]


def _header(line: str) -> Optional[list[str]]:
    toks = line.split()
    _label, hdr = _suffix(toks, _is_header_token)
    if len(hdr) < 3 or len(set(hdr)) != len(hdr):
        return None
    ints = all(re.fullmatch(r"\d{3,5}", t) for t in hdr)
    if ints and [int(t) for t in hdr] != sorted(int(t) for t in hdr):
        return None
    if not ints and not all(re.search(r"[A-Za-z]", t) for t in hdr):
        return None
    return hdr


def _row(line: str, k: int) -> Optional[tuple[str, list[str], str]]:
    toks = line.split()
    unit = ""
    if toks and _TRAIL_UNIT.match(toks[-1]) and not _CELL.match(toks[-1]):
        unit = toks[-1]
        toks = toks[:-1]
    label, cells = _suffix(toks, lambda t: bool(_CELL.match(t)))
    if len(cells) != k or not label:
        return None
    return " ".join(label), cells, unit


def find_tables(page: Page) -> list[MultiTable]:
    lines = [ln.strip() for ln in page.text.splitlines()]
    out: list[MultiTable] = []
    i = 0
    while i < len(lines):
        hdr = _header(lines[i]) if lines[i] else None
        if hdr:
            rows = []
            j = i + 1
            while j < len(lines):
                if not lines[j]:
                    j += 1
                    continue
                r = _row(lines[j], len(hdr))
                if r is None:
                    break
                rows.append((r[0], r[1], lines[j], r[2]))
                j += 1
            if len(rows) >= 2:
                out.append(MultiTable(page.number, lines[i], hdr, rows))
                i = j
                continue
        i += 1
    return out


_COLS = [
    (re.compile(r"^(kva|mva|capacity|rating|power)$", re.I), "Rated power", "kVA"),
    (re.compile(r"^(hv|primary)$", re.I), "Primary voltage", None),
    (re.compile(r"^(lv|secondary)$", re.I), "Secondary voltage", None),
    (re.compile(r"^(z|impedance|%z)$", re.I), "Impedance", "%"),
    (re.compile(r"^(connection|vector|winding|group)$", re.I), "Winding connection", ""),
    (re.compile(r"^(loss|losses)$", re.I), "Total losses", None),
    (re.compile(r"^(mass|weight)$", re.I), "Total weight", None),
    (re.compile(r"^(heaviest|largest)$", re.I), "Heaviest transport weight", None),
]
_MODEL_HEAD = re.compile(r"^(model|type|catalog(ue)?(\s+no\.?)?|cat\.?\s*no\.?|part)\b", re.I)
_UNIT_TOKEN = re.compile(r"^\(\s*([A-Za-z%]{1,5})\s*\)$")


_SWG = re.compile(
    r"(?P<v>Rated\s+kV|Voltage\s+kV|Max\.?\s+kV)|(?P<c>Cont(?:\.|inuous)?\s+A)|(?P<b>Main\s+bus\s+A|Bus\s+A)|"
    r"(?P<s>SCCR\s+kA|Short[- ]circuit\s+kA|kA\s+SC)|(?P<i>BIL\s+kV)|(?P<e>Enclosure|NEMA)", re.I)
_SWG_COLS = {"v": ("Rated maximum voltage", "kV"), "c": ("Continuous current", "A"), "b": ("Main bus rating", "A"),
             "s": ("Short-circuit rating", "kA"), "i": ("BIL", "kV"), "e": ("Enclosure", "")}


def _row_columns(header: str) -> Optional[list[list]]:
    toks = header.split()
    if not toks or not _MODEL_HEAD.match(toks[0]):
        return None
    sw = [m.lastgroup for m in _SWG.finditer(" ".join(toks[1:]))]
    if len(sw) >= 3:
        return [list(_SWG_COLS[g]) for g in sw]
    cols: list[list] = []  # [label, unit]
    for t in toks[1:]:
        u = _UNIT_TOKEN.match(t)
        if u and cols:
            cols[-1][1] = u.group(1)
            continue
        for rx, label, unit in _COLS:
            if rx.match(t):
                cols.append([label, unit])
                break
    return cols if len(cols) >= 3 else None


def find_row_tables(page: Page) -> list[MultiTable]:
    """Catalogue tables with one model per row and a column per parameter, transposed into models-in-columns form."""
    lines = [ln.strip() for ln in page.text.splitlines()]
    out: list[MultiTable] = []
    i = 0
    while i < len(lines):
        cols = _row_columns(lines[i]) if lines[i] else None
        if not cols:
            i += 1
            continue
        j = i + 1
        pending_units = None
        if j < len(lines) and lines[j] and all(_UNIT_TOKEN.match(t) for t in lines[j].split()):
            pending_units = [_UNIT_TOKEN.match(t).group(1) for t in lines[j].split()]
            j += 1
        rows: list[tuple[str, list[str], str]] = []
        while j < len(lines):
            if not lines[j]:
                j += 1
                continue
            toks = lines[j].split()
            if cols[-1][0] == "Enclosure" and len(toks) > len(cols) + 1:
                toks = toks[: len(cols)] + [" ".join(toks[len(cols):])]
            if len(toks) != len(cols) + 1 or not re.search(r"\d", toks[0]):
                break
            rows.append((toks[0], toks[1:], lines[j]))
            j += 1
        if len(rows) < 2:
            i += 1
            continue
        numeric = [k for k in range(len(cols)) if cols[k][0] != "Enclosure" and all(_CELL.match(r[1][k]) for r in rows)]
        lacking = [k for k in numeric if cols[k][1] is None]
        if pending_units and len(pending_units) == len(lacking):
            for k, u in zip(lacking, pending_units):
                cols[k][1] = u
        kept = [k for k in range(len(cols)) if cols[k][1] is not None or k not in numeric]
        header_text = lines[i]
        out.append(MultiTable(page.number, header_text, [r[0] for r in rows],
                              [(cols[k][0], [r[1][k] for r in rows], "", cols[k][1] or "") for k in kept],
                              model_raws=[r[2] for r in rows], lines=lines[i:j]))
        i = j
    return out


def choose_column(models: list[str], offered: Optional[str]) -> Optional[int]:
    if not offered:
        return None
    o = _norm(offered)
    for idx, m in enumerate(models):
        if _norm(m) == o:
            return idx
    nums = re.findall(r"\d+", offered)
    if nums and all(re.fullmatch(r"\d{3,5}", m) for m in models):
        hits = [idx for idx, m in enumerate(models) if m == nums[0]]
        if len(hits) == 1 and re.search(r"kva|mva|kw|^\d+$", offered.strip().lower()):
            return hits[0]
    return None


def _synthetic(label: str, value: str, unit: str) -> str:
    m = _UNIT_LABEL.match(label)
    if m:
        return f"{m.group(1)}: {value} {m.group(2)}"
    return f"{label}: {value} {unit}".strip()


def apply_model_view(doc: ParsedDocument, offered: Optional[str]) -> ParsedDocument:
    """Return a copy of `doc` where multi-model tables are replaced by the offered model's lines (or withheld)."""
    if doc.role not in {"spec", "original", "alternate", "library"}:
        return doc
    pages: list[Page] = []
    quote_map: dict[str, str] = dict(doc.quote_map)
    notes: list[str] = list(doc.table_notes)
    ambiguous: list[dict] = []
    changed = False
    for page in doc.pages:
        if page.status != "ok":
            pages.append(page)
            continue
        tables = find_tables(page) + find_row_tables(page)
        if not tables:
            pages.append(page)
            continue
        changed = True
        drop = {r[2] for t in tables if not t.lines for r in t.rows} | {t.header_line for t in tables if not t.lines} | {ln for t in tables if t.lines for ln in t.lines}
        keep = [ln for ln in page.text.splitlines() if ln.strip() not in drop]
        extra: list[str] = []
        for t in tables:
            col = choose_column(t.models, offered)
            if col is None:
                why = "no offered model was given" if not offered else f"the offered model '{offered}' is not in the table"
                notes.append(f"p.{t.page}: a table lists models {', '.join(t.models)}; {why}, so its rows were not used")
                ambiguous.append({"page": t.page, "models": t.models, "rows": [(r[0], r[1], r[2], r[3]) for r in t.rows]})
                continue
            notes.append(f"p.{t.page}: read column '{t.models[col]}' of a table listing {', '.join(t.models)}")
            for label, cells, raw, unit in t.rows:
                syn = _synthetic(label, cells[col], unit)
                extra.append(syn)
                quote_map[syn] = f"{t.header_line} | {t.model_raws[col] if t.model_raws else raw}"
        pages.append(page.model_copy(update={"text": "\n".join(keep + extra), "raw_text": page.raw_text or page.text}))
    if not changed:
        return doc
    return doc.model_copy(update={"pages": pages, "quote_map": quote_map, "table_notes": notes, "ambiguous_rows": ambiguous})


_UNIT_HEAD = re.compile(r"^(item|parameter|characteristic|description|property)\b(?P<mid>.*?)\bunit\b(?P<tail>.*)$", re.I)
_UNIT_ROW = re.compile(r"^(?P<label>[A-Za-z][^\n]*?)\s+(?P<unit>kVA|MVA|kV|V|%|kW|W|kg|lbs?|mm|A|kA|Hz|-|\u2013)\s+(?P<rest>\S.*)$")
_OFFERED = re.compile(r"offered|proposed|submitted|this project|bid", re.I)
_BASELINE = re.compile(r"standard|baseline|catalog", re.I)


def apply_unit_columns(doc: ParsedDocument) -> ParsedDocument:
    """Tables laid out as 'Item | Unit | Value ...' become 'Item: value unit' lines. When a Standard/Baseline column sits
    beside an Offered one, only the offered value is read; the original row stays the citation."""
    if doc.role not in {"spec", "original", "alternate", "library"}:
        return doc
    qmap = dict(doc.quote_map)
    notes = list(doc.table_notes)
    pages = []
    changed = False
    for pg in doc.pages:
        if pg.status != "ok":
            pages.append(pg)
            continue
        out: list[str] = []
        header: Optional[str] = None
        nvals, pick = 1, 0
        for line in pg.text.split("\n"):
            s = line.strip()
            h = _UNIT_HEAD.match(s)
            if h:
                header = s
                tail = h.group("tail")
                if _OFFERED.search(tail) and _BASELINE.search(tail):
                    nvals = 2
                    pick = 1 if _OFFERED.search(tail).start() > _BASELINE.search(tail).start() else 0
                else:
                    nvals, pick = 1, 0
                out.append(line)
                continue
            m = _UNIT_ROW.match(s) if header else None
            if not m:
                if header and s and not re.search(r"\d", s):
                    header = None  # a new heading ends the table
                out.append(line)
                continue
            unit, rest = m.group("unit"), m.group("rest").split()
            text_unit = unit in {"-", "\u2013"}
            numeric_idx = [k for k, t in enumerate(rest) if re.fullmatch(r"[\d.,]+", t)]
            if nvals == 2:
                if len(rest) < 2:
                    out.append(line)
                    continue
                if not text_unit and len(numeric_idx) >= 2:
                    value = rest[numeric_idx[pick]]
                    tail_toks = [t for k, t in enumerate(rest) if k not in numeric_idx[:2]]
                else:
                    value, tail_toks = rest[pick], rest[2:]
            elif text_unit:
                value, tail_toks = " ".join(rest), []
            elif numeric_idx:
                value = rest[numeric_idx[0]]
                tail_toks = rest[: numeric_idx[0]] + rest[numeric_idx[0] + 1:]  # 'maximum 13.0' keeps its qualifier
            else:
                value, tail_toks = rest[0], rest[1:]
            syn = f"{m.group('label')}: {value}" + ("" if text_unit else f" {unit}") + (f" {' '.join(tail_toks)}" if tail_toks else "")
            qmap[syn.strip()] = f"{header} | {s}"
            out.append(syn.strip())
            changed = True
        pages.append(pg.model_copy(update={"text": "\n".join(out), "raw_text": pg.raw_text or pg.text}))
    if not changed:
        return doc
    notes.append("tables with a Unit column were read row by row" + ("; the Offered column was used, not the Standard one" if any("Offered" in (q or "") or "offered" in (q or "").lower() for q in qmap.values()) else ""))
    return doc.model_copy(update={"pages": pages, "quote_map": qmap, "table_notes": notes})
