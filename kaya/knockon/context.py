"""Case context: the parsed documents, extracted fields, project constraints and schedule."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from . import extract as X
from .ingest import ParsedDocument
from .schemas import Evidence, FieldValue

ROLES = ("spec", "original", "alternate", "logistics", "schedule")


@dataclass
class CaseContext:
    case_id: str
    docs: dict[str, ParsedDocument]
    fields: dict[str, dict[str, FieldValue]]
    constraints: dict[str, FieldValue]
    schedule: Optional[dict[str, Any]]
    facts: dict[str, Any]
    target: Optional[float]
    equipment_type: str
    inputs_hash: str = ""
    notes: list[str] = field(default_factory=list)

    def f(self, role: str, name: str) -> FieldValue:
        """Field value for a role, or a not-provided placeholder when the document is absent."""
        fv = self.fields.get(role, {}).get(name)
        if fv is not None:
            return fv
        return FieldValue(
            field=name,
            status="not_stated",
            unit=X.FIELD_UNITS.get(name),
            confidence=0.0,
            notes=[f"no {role} document was provided"],
        )

    def has(self, role: str) -> bool:
        return role in self.docs


def _fact_evidence(key: str, value: Any, facts_hash: str) -> Evidence:
    return Evidence(
        document="project_facts",
        role="facts",
        revision=None,
        sha256=facts_hash,
        page=0,
        quote=f"{key} = {value} (provided by the caller as a project fact)",
    )


def _facts_to_constraints(facts: dict[str, Any]) -> dict[str, FieldValue]:
    out: dict[str, FieldValue] = {}
    fh = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    for key in X.CONSTRAINT_FIELDS:
        if key in facts and isinstance(facts[key], (int, float)) and not isinstance(facts[key], bool):
            out[key] = FieldValue(
                field=key,
                status="documented",
                value=float(facts[key]),
                unit=X.FIELD_UNITS.get(key),
                evidence=[_fact_evidence(key, facts[key], fh)],
                confidence=0.8,
                notes=["caller-supplied project fact (no source document)"],
            )
    return out


def _merge_constraint(name: str, doc_fv: Optional[FieldValue], fact_fv: Optional[FieldValue]) -> FieldValue:
    if doc_fv is None and fact_fv is None:
        return FieldValue(field=name, status="not_stated", unit=X.FIELD_UNITS.get(name), confidence=0.0,
                          notes=["no logistics document or project fact provides this"])
    if doc_fv is None:
        return fact_fv  # type: ignore[return-value]
    if fact_fv is None:
        return doc_fv
    if doc_fv.status == "documented" and fact_fv.status == "documented":
        if abs(float(doc_fv.value) - float(fact_fv.value)) <= 1e-3 * max(abs(float(doc_fv.value)), 1.0):
            doc_fv.evidence = doc_fv.evidence + fact_fv.evidence
            return doc_fv
        return FieldValue(
            field=name,
            status="conflicting",
            unit=doc_fv.unit,
            evidence=doc_fv.evidence + fact_fv.evidence,
            detail={"document": doc_fv.value, "project_fact": fact_fv.value},
            notes=["the logistics document and the supplied project fact disagree"],
        )
    return fact_fv if fact_fv.status == "documented" else doc_fv


def build_context(
    case_id: str,
    docs: dict[str, ParsedDocument],
    facts: Optional[dict[str, Any]],
    target: Optional[float],
) -> CaseContext:
    facts = dict(facts or {})
    fields: dict[str, dict[str, FieldValue]] = {}
    for role, doc in docs.items():
        fields[role] = X.extract_document(doc)
    doc_constraints = fields.get("logistics", {})
    fact_constraints = _facts_to_constraints(facts)
    constraints = {n: _merge_constraint(n, doc_constraints.get(n), fact_constraints.get(n)) for n in X.CONSTRAINT_FIELDS}

    schedule: Optional[dict[str, Any]] = None
    sched_doc = docs.get("schedule")
    if sched_doc is not None and isinstance(sched_doc.data, dict):
        schedule = dict(sched_doc.data)
    if isinstance(facts.get("schedule"), dict):
        schedule = {**(schedule or {}), **facts["schedule"]}
    eff_target = target
    if eff_target is None and schedule and isinstance(schedule.get("recovery_target_weeks"), (int, float)):
        eff_target = float(schedule["recovery_target_weeks"])
    if eff_target is None and isinstance(facts.get("recovery_target_weeks"), (int, float)):
        eff_target = float(facts["recovery_target_weeks"])

    eq_docs = [d for r, d in docs.items() if r in {"spec", "original", "alternate"}]
    eq_type = X.detect_equipment_type(eq_docs)

    h = hashlib.sha256()
    h.update(json.dumps({r: d.sha256 for r, d in sorted(docs.items())}, sort_keys=True).encode())
    h.update(json.dumps(facts, sort_keys=True).encode())
    h.update(json.dumps(eff_target).encode())
    return CaseContext(
        case_id=case_id,
        docs=docs,
        fields=fields,
        constraints=constraints,
        schedule=schedule,
        facts=facts,
        target=eff_target,
        equipment_type=eq_type,
        inputs_hash=h.hexdigest(),
    )
