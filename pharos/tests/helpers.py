"""Build cases from plain-text documents so each behaviour can be tested in isolation."""
from __future__ import annotations

from typing import Any, Optional

from pharos import core
from pharos.schemas import CaseInput, DocumentInput
from pharos.store import Store

BASE_ALT = """Manufacturer: Test Vendor (synthetic)
Model: TV-1
Revision: A
Rated capacity: 2,500 kVA
Voltage ratio: 13,800 V - 480Y/277 V
Impedance (%Z) at 75 C: 5.00 %
Vector group: Dyn11
Overall dimensions (L x W x H): 2,100 x 1,500 x 2,200 mm
Heaviest shipping section: 3,000 kg
Total weight: 7,000 kg
Total losses: 12.0 kW
Lead time: 30 weeks ARO
"""

SCHEDULE = {
    "milestone": {"name": "Energization", "install_test_weeks": 10},
    "order_release_week": 0,
    "submittal_approval_weeks": 4,
    "substituted_item": "T1",
    "substituted_item_label": "transformer",
    "items": [
        {"id": "T1", "name": "Transformer T1", "baseline_arrival_week": 82},
        {"id": "SG", "name": "Switchgear", "arrival_week": 80, "vendor": "Switchgear vendor"},
    ],
}


def docs(**texts: Optional[str]) -> list[DocumentInput]:
    return [DocumentInput(role=r, text=t, name=f"{r}.txt") for r, t in texts.items() if t is not None]  # type: ignore[arg-type]


def run(alt: str = BASE_ALT, spec: Optional[str] = None, original: Optional[str] = None, logistics: Optional[str] = None,
        schedule: Optional[dict[str, Any]] = SCHEDULE, facts: Optional[dict[str, Any]] = None, target: Optional[float] = None,
        store: Optional[Store] = None, case_id: Optional[str] = None):
    st = store or Store(":memory:")
    f = dict(facts or {})
    if schedule is not None:
        f["schedule"] = schedule
    inp = CaseInput(case_id=case_id, documents=docs(alternate=alt, spec=spec, original=original, logistics=logistics),
                    project_facts=f or None, recovery_target_weeks=target)
    return core.decide_and_ask(inp, st), st
