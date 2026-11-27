"""Schedule triage for PO lines required at a single joint handoff."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from pharos.checks import CitedFact, WeekFact, WholeWeeks


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OpenCondition(CitedFact):
    description: NonBlank


class ReadyDate(CitedFact):
    week: WholeWeeks | None = Field(description="Ready for handoff in this project week; null if undated.")
    open_conditions: list[OpenCondition] = Field(default_factory=list)


class PurchaseOrderLine(BaseModel, extra="forbid"):
    line_id: NonBlank
    baseline: ReadyDate
    proposed: ReadyDate | None = Field(
        default=None, description="Replacement scenario fact, including its conditions; omit if unchanged."
    )


Action = Literal["request_ready_date", "resolve_condition", "seek_earlier_date", "confirm_date", "keep_order"]


class LineRisk(BaseModel):
    line_id: str
    ready: ReadyDate
    change_from_baseline_weeks: int | None
    float_to_handoff_weeks: int | None
    margin_to_deadline_weeks: int | None
    action: Action


class Scenario(BaseModel):
    status: Literal["needs_dates", "conditional_on_open_items", "on_stated_dates"]
    handoff_week: int | None
    milestone_week: int | None
    controlling_line_ids: list[str]
    lines_by_urgency: list[LineRisk]


class DeliveryRiskResult(BaseModel):
    baseline: Scenario
    proposed: Scenario | None
    potential_recovery_weeks: int | None
    recovery_target_status: Literal["needs_data", "not_met", "conditional_on_open_items", "met_on_stated_dates"] | None
    latest_handoff_week_for_recovery: int | None
    action_deadline_week: int | None
    post_handoff_weeks: WeekFact
    required_handoff_week: WeekFact | None
    recovery_target_weeks: WeekFact | None


def _joint_handoff(dates: dict[str, ReadyDate]) -> int | None:
    weeks = [date.week for date in dates.values() if date.week is not None]
    return max(weeks) if len(weeks) == len(dates) else None


def _line_action(ready: ReadyDate, float_weeks: int | None, margin: int | None) -> Action:
    if ready.week is None:
        return "request_ready_date"
    if ready.open_conditions:
        return "resolve_condition"
    if margin is not None and margin < 0:
        return "seek_earlier_date"
    if float_weeks is None or margin == 0:
        return "confirm_date"
    if float_weeks > 0 or (margin is not None and margin > 0):
        return "keep_order"
    return "confirm_date"


def _scenario(
    dates: dict[str, ReadyDate], baseline: dict[str, ReadyDate], handoff: int | None,
    post_handoff_weeks: int, deadline: int | None,
) -> Scenario:
    risks = []
    controllers = []
    for line_id, date in dates.items():
        week = date.week
        previous = baseline[line_id].week
        float_weeks = handoff - week if handoff is not None and week is not None else None
        if float_weeks == 0:
            controllers.append(line_id)
        margin = deadline - week if deadline is not None and week is not None else None
        risks.append(LineRisk(
            line_id=line_id, ready=date,
            change_from_baseline_weeks=week - previous if week is not None and previous is not None else None,
            float_to_handoff_weeks=float_weeks, margin_to_deadline_weeks=margin,
            action=_line_action(date, float_weeks, margin),
        ))
    # Undated lines need clarification first. Among known dates the latest is
    # closest to controlling this joint handoff; line ID only breaks display ties.
    risks.sort(key=lambda line: (line.ready.week is not None, -(line.ready.week or 0), line.line_id))
    status = "on_stated_dates"
    if handoff is None:
        status = "needs_dates"
    elif any(date.open_conditions for date in dates.values()):
        status = "conditional_on_open_items"
    return Scenario(
        status=status, handoff_week=handoff,
        milestone_week=handoff + post_handoff_weeks if handoff is not None else None,
        controlling_line_ids=sorted(controllers), lines_by_urgency=risks,
    )


def assess_delivery_risk(
    po_lines: Annotated[list[PurchaseOrderLine], Field(min_length=1)],
    post_handoff_weeks: WeekFact,
    required_handoff_week: WeekFact | None = None,
    recovery_target_weeks: WeekFact | None = None,
) -> DeliveryRiskResult:
    """Rank all PO lines needed together and optionally compare a revision or alternate.

    Use a common week origin and calendar. The milestone follows the latest ready
    line by the same fixed duration in both scenarios. Dates with open conditions
    are what-if inputs, not commitments. No known date means no complete milestone.
    """
    if not po_lines:
        raise ValueError("Supply at least one PO line required for the handoff.")
    original = {line.line_id: line.baseline for line in po_lines}
    if len(original) != len(po_lines):
        raise ValueError("Each PO line ID must be unique within the handoff.")

    handoff = _joint_handoff(original)
    latest_for_target = None
    if recovery_target_weeks is not None and handoff is not None:
        latest_for_target = handoff - recovery_target_weeks.value
    deadlines = []
    if required_handoff_week is not None:
        deadlines.append(required_handoff_week.value)
    if latest_for_target is not None:
        deadlines.append(latest_for_target)
    deadline = min(deadlines, default=None)

    baseline = _scenario(original, original, handoff, post_handoff_weeks.value, deadline)
    proposed = None
    recovery = None
    target_status = None
    if any(line.proposed is not None for line in po_lines):
        revised = {line.line_id: line.proposed or line.baseline for line in po_lines}
        proposed = _scenario(revised, original, _joint_handoff(revised), post_handoff_weeks.value, deadline)
        if baseline.milestone_week is not None and proposed.milestone_week is not None:
            recovery = baseline.milestone_week - proposed.milestone_week
        if recovery_target_weeks is not None:
            if recovery is None or baseline.status == "conditional_on_open_items":
                target_status = "needs_data"
            elif recovery < recovery_target_weeks.value:
                target_status = "not_met"
            elif proposed.status == "conditional_on_open_items":
                target_status = "conditional_on_open_items"
            else:
                target_status = "met_on_stated_dates"
    return DeliveryRiskResult(
        baseline=baseline, proposed=proposed, potential_recovery_weeks=recovery,
        recovery_target_status=target_status, latest_handoff_week_for_recovery=latest_for_target,
        action_deadline_week=deadline, post_handoff_weeks=post_handoff_weeks,
        required_handoff_week=required_handoff_week, recovery_target_weeks=recovery_target_weeks,
    )
