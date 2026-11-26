"""Shared data contracts. Every tool reads and writes these shapes."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["spec", "original", "alternate", "logistics", "schedule"]
FieldStatus = Literal["documented", "not_stated", "could_not_read", "conflicting"]
Label = Literal["conclusive", "cleared", "needs_engineer", "not_stated", "could_not_read"]
Answer = Literal["yes", "only_if", "no_not_alone", "no", "needs_data", "no_target"]


class Evidence(BaseModel):
    """A resolvable pointer to the exact place a value came from."""

    document: str
    role: str
    revision: Optional[str] = None
    sha256: str
    page: int
    quote: str
    verified: bool = True


class FieldValue(BaseModel):
    field: str
    status: FieldStatus
    value: Any = None  # normalised value (float, str or dict)
    unit: Optional[str] = None
    qualifier: Optional[Literal["min", "max", "nominal"]] = None
    detail: Any = None
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)
    unreadable_pages: list[int] = Field(default_factory=list)


class DocumentRef(BaseModel):
    role: str
    name: str
    revision: Optional[str] = None
    sha256: str
    pages: int
    unreadable_pages: list[int] = Field(default_factory=list)
    kind: str = "pdf"


class DocumentInput(BaseModel):
    role: Role
    path: Optional[str] = None
    text: Optional[str] = None
    content_base64: Optional[str] = None
    name: Optional[str] = None
    revision: Optional[str] = None


class CaseInput(BaseModel):
    """What a caller sends to any of the three tools."""

    case_id: Optional[str] = None
    package_dir: Optional[str] = None
    documents: list[DocumentInput] = Field(default_factory=list)
    revised_documents: list[DocumentInput] = Field(default_factory=list)
    project_facts: Optional[dict[str, Any]] = None
    recovery_target_weeks: Optional[float] = None


class FieldComparison(BaseModel):
    field: str
    label: str
    spec: FieldValue
    original: FieldValue
    alternate: FieldValue
    changed_vs_original: Optional[bool] = None
    deviates_from_spec: Optional[bool] = None


class Difference(BaseModel):
    field: str
    label: str
    kind: Literal["changed_vs_original", "deviates_from_spec"]
    from_value: Any = None
    to_value: Any = None
    unit: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)


class SupplierGap(BaseModel):
    field: str
    label: str
    status: FieldStatus
    reason: str
    unreadable_pages: list[int] = Field(default_factory=list)


class CompareResult(BaseModel):
    case_id: Optional[str] = None
    equipment_type: str
    documents: list[DocumentRef]
    fields: list[FieldComparison]
    differences: list[Difference]
    supplier_gaps: list[SupplierGap]
    summary: str


class FollowUp(BaseModel):
    kind: Literal["vendor", "engineer", "readable_copy", "route", "none"]
    question: Optional[str] = None


class Finding(BaseModel):
    key: str
    topic: Literal["physical", "electrical", "specification", "schedule"]
    label: Label
    title: str
    summary: str
    constraint: Optional[dict[str, Any]] = None
    requirement_evidence: list[Evidence] = Field(default_factory=list)
    supplier_evidence: list[Evidence] = Field(default_factory=list)
    formula: Optional[str] = None
    computed: dict[str, Any] = Field(default_factory=dict)
    scope_note: Optional[str] = None
    follow_up: FollowUp = Field(default_factory=lambda: FollowUp(kind="none"))
    confidence: float = 0.0


class ScreenResult(BaseModel):
    case_id: Optional[str] = None
    findings: list[Finding]
    missing_project_facts: list[str]
    summary: str


class MilestoneResult(BaseModel):
    name: str
    baseline_week: Optional[float] = None
    alternate_week_best: Optional[float] = None
    alternate_week_conservative: Optional[float] = None
    max_recoverable_weeks: Optional[float] = None
    conservative_recoverable_weeks: Optional[float] = None
    weeks_earlier_alternate_ships: Optional[float] = None
    controlling_item_baseline: Optional[str] = None
    controlling_item_alternate: Optional[str] = None
    install_test_weeks: Optional[float] = None


class Requirement(BaseModel):
    item: str
    currently_week: Optional[float] = None
    must_be_ready_by_week: float
    owner: Optional[str] = None


class CostItem(BaseModel):
    item: str
    amount: float
    currency: str
    source: str


class DecisionDiff(BaseModel):
    from_version: int
    to_version: int
    changed: list[dict[str, Any]] = Field(default_factory=list)
    updated: list[dict[str, Any]] = Field(default_factory=list)
    still_open: list[str] = Field(default_factory=list)
    unchanged_settled: list[str] = Field(default_factory=list)
    new: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    milestone_moved: bool = False
    answer_before: Optional[str] = None
    answer_after: Optional[str] = None
    max_recoverable_before: Optional[float] = None
    max_recoverable_after: Optional[float] = None


class DecisionResult(BaseModel):
    case_id: str
    version: int
    inputs_hash: str
    target_weeks: Optional[float] = None
    answer: Answer
    headline: str
    milestone: Optional[MilestoneResult] = None
    conditions: list[str] = Field(default_factory=list)
    requirements_to_hit_target: list[Requirement] = Field(default_factory=list)
    next_call: Optional[dict[str, str]] = None
    settled: list[str] = Field(default_factory=list)
    open: list[str] = Field(default_factory=list)
    costs: list[CostItem] = Field(default_factory=list)
    cost_note: str = ""
    findings: list[Finding] = Field(default_factory=list)
    vendor_questions: list[str] = Field(default_factory=list)
    engineer_questions: list[str] = Field(default_factory=list)
    readable_copy_requests: list[str] = Field(default_factory=list)
    missing_project_facts: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    documents: list[DocumentRef] = Field(default_factory=list)
    diff: Optional[DecisionDiff] = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    notice: str = (
        "Pre-screen only. KNOCK-ON does not approve engineering; open items go to the "
        "vendor or the engineer of record."
    )
