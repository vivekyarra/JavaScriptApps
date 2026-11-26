"""Unit parsing and conversion. Conversions are plain arithmetic; ambiguous units are refused."""
from __future__ import annotations

import re
from typing import Optional

NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"


def parse_number(text: str) -> Optional[float]:
    """Parse an en-US formatted number such as '4,100' or '5.75'."""
    text = text.strip()
    if not re.fullmatch(NUM, text):
        return None
    return float(text.replace(",", ""))


_WEIGHT_KG = {
    "kg": 1.0,
    "kgs": 1.0,
    "t": 1000.0,
    "tonne": 1000.0,
    "tonnes": 1000.0,
    "metric ton": 1000.0,
    "metric tons": 1000.0,
    "lb": 0.45359237,
    "lbs": 0.45359237,
    "pound": 0.45359237,
    "pounds": 0.45359237,
    "kip": 453.59237,
    "kips": 453.59237,
}
# 'ton' / 'tons' alone are ambiguous (short ton vs metric tonne) and are deliberately absent.
AMBIGUOUS_WEIGHT_UNITS = {"ton", "tons"}

_LENGTH_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    '"': 25.4,
    "ft": 304.8,
    "feet": 304.8,
    "'": 304.8,
}

_POWER_KW = {"kw": 1.0, "w": 0.001, "mw": 1000.0, "btu/h": 0.000293071, "btu/hr": 0.000293071, "btuh": 0.000293071}
_KVA = {"kva": 1.0, "mva": 1000.0}
_VOLT = {"v": 1.0, "kv": 1000.0}
_PRESSURE_KG_M2 = {
    "kg/m2": 1.0,
    "kg/m²": 1.0,
    "kg per square metre": 1.0,
    "kg per square meter": 1.0,
    "kg per m2": 1.0,
    "kg per m²": 1.0,
    "lb per square foot": 4.882428,
    "lbs per square foot": 4.882428,
    "lb per sq ft": 4.882428,
    "lbs per sq ft": 4.882428,
    "kpa": 101.9716,
    "kn/m2": 101.9716,
    "kn/m²": 101.9716,
    "psf": 4.882428,
    "lb/ft2": 4.882428,
    "lb/ft²": 4.882428,
    "lbs/ft2": 4.882428,
    "lbs/sq ft": 4.882428,
    "lb/sq ft": 4.882428,
}


def _norm(unit: str) -> str:
    return re.sub(r"\s+", " ", unit.strip().lower().rstrip("."))


def weight_to_kg(value: float, unit: str) -> Optional[float]:
    f = _WEIGHT_KG.get(_norm(unit))
    return None if f is None else value * f


def length_to_mm(value: float, unit: str) -> Optional[float]:
    f = _LENGTH_MM.get(_norm(unit))
    return None if f is None else value * f


def power_to_kw(value: float, unit: str) -> Optional[float]:
    f = _POWER_KW.get(_norm(unit))
    return None if f is None else value * f


def kva_from(value: float, unit: str) -> Optional[float]:
    f = _KVA.get(_norm(unit))
    return None if f is None else value * f


def volts_from(value: float, unit: str) -> Optional[float]:
    f = _VOLT.get(_norm(unit))
    return None if f is None else value * f


def pressure_to_kg_m2(value: float, unit: str) -> Optional[float]:
    f = _PRESSURE_KG_M2.get(_norm(unit))
    return None if f is None else value * f


def time_to_weeks(value: float, unit: str) -> tuple[Optional[float], bool]:
    """Return (weeks, approximate). Months are converted at 52/12 weeks and flagged approximate."""
    u = _norm(unit)
    if u in {"w", "wk", "wks", "week", "weeks"}:
        return value, False
    if u in {"d", "day", "days"}:
        return value / 7.0, False
    if u in {"mo", "mos", "month", "months"}:
        return value * 52.0 / 12.0, True
    return None, False


def same_number(a: float, b: float, rel: float = 1e-3, abs_tol: float = 1e-9) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


def fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")
