"""Deterministic checks on normalized facts supplied by the caller."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator


class CitedFact(BaseModel, extra="forbid"):
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Reference to the originating document revision and page, or record and row."
    )


class MassFact(CitedFact):
    value: Decimal = Field(ge=0, max_digits=12, decimal_places=3, description="Kilograms per lift.")


class WeightResult(BaseModel):
    status: Literal["exceeds_limit", "within_weight_limit", "needs_data", "needs_review"]
    gross_kg: Decimal | None
    reason: str
    sources: dict[str, str]


def check_elevator_load(
    section_kg: MassFact,
    limit_kg: MassFact,
    additional_load_kg: MassFact | None = None,
    documented_gross_kg: MassFact | None = None,
) -> WeightResult:
    """Check one lift against its elevator payload limit. This checks weight only.

    Additional load includes ALL other payload, including rigging. A documented
    gross load already includes it. Omit unknown masses; do not enter zero for them.
    """
    if section_kg.value == 0 or limit_kg.value == 0:
        raise ValueError("Section mass and elevator limit must both be positive.")

    sources = {"section_kg": section_kg.source, "limit_kg": limit_kg.source}
    gross = None
    if additional_load_kg is not None:
        sources["additional_load_kg"] = additional_load_kg.source
        gross = section_kg.value + additional_load_kg.value
    if documented_gross_kg is not None:
        sources["documented_gross_kg"] = documented_gross_kg.source
        declared = documented_gross_kg.value
        if declared < section_kg.value or (gross is not None and declared != gross):
            return WeightResult(
                status="needs_review", gross_kg=None, sources=sources,
                reason="Reconcile the documented gross weight with the section and payload records.",
            )
        gross = declared

    if section_kg.value > limit_kg.value:
        status = "exceeds_limit"
        reason = "The section alone exceeds the documented elevator limit."
    elif gross is None:
        status = "needs_data"
        reason = "Request the complete gross weight per lift or the weight of all additional payload."
    elif gross > limit_kg.value:
        status = "exceeds_limit"
        reason = "The gross transported load exceeds the documented elevator limit."
    else:
        status = "within_weight_limit"
        reason = "The gross transported load is at or below the limit for this weight check only."
    return WeightResult(status=status, gross_kg=gross, reason=reason, sources=sources)


WholeWeeks = Annotated[int, Field(strict=True, ge=0)]


class WeekFact(CitedFact):
    value: WholeWeeks


class ProductionRange(CitedFact):
    minimum: WholeWeeks
    maximum: WholeWeeks

    @model_validator(mode="after")
    def check_order(self):
        if self.minimum > self.maximum:
            raise ValueError("Minimum production duration cannot exceed the maximum.")
        return self


class ComparableObservation(CitedFact):
    """One delivered order comparable to this one: what was quoted and what actually happened, from the same start event."""

    quoted_weeks: WholeWeeks
    actual_weeks: WholeWeeks


MIN_COMPARABLES = 5


class ReferenceRange(BaseModel):
    observations: int
    slip_ratio_min: float
    slip_ratio_median: float
    slip_ratio_max: float
    weeks_after_start: tuple[int, int]
    basis: str


class ArrivalResult(BaseModel):
    status: Literal["conditional_on_quoted_terms", "needs_approval_date", "needs_order_date"]
    weeks_after_approval: tuple[int, int] | None  # set when the quote starts at drawing approval
    onsite_week_range: tuple[int, int] | None
    reason: str
    sources: dict[str, str]
    start: Literal["approval", "order"] = "approval"
    weeks_after_start: tuple[int, int] | None = None
    reference: ReferenceRange | None = None
    reference_onsite_week_range: tuple[int, int] | None = None
    reference_note: str | None = None


def _reference(obs: list[ComparableObservation], earliest: int, latest: int, transit: int) -> tuple[ReferenceRange | None, str | None]:
    """Spread of what comparable orders actually did against their quotes. Not a percentile forecast."""
    if not obs:
        return None, None
    if len(obs) < MIN_COMPARABLES:
        return None, f"{len(obs)} comparable observation(s) supplied; at least {MIN_COMPARABLES} are needed before any reference range is shown."
    ratios = sorted(o.actual_weeks / o.quoted_weeks for o in obs if o.quoted_weeks > 0)
    if len(ratios) < MIN_COMPARABLES:
        return None, "Too few comparable observations have a positive quoted duration."
    median = ratios[len(ratios) // 2] if len(ratios) % 2 else (ratios[len(ratios) // 2 - 1] + ratios[len(ratios) // 2]) / 2
    prod_min, prod_max = earliest - transit, latest - transit
    lo = int(prod_min * ratios[0]) + transit
    hi = -int(-(prod_max * ratios[-1]) // 1) + transit  # round up
    return ReferenceRange(
        observations=len(ratios), slip_ratio_min=round(ratios[0], 3), slip_ratio_median=round(median, 3),
        slip_ratio_max=round(ratios[-1], 3), weeks_after_start=(lo, hi),
        basis=f"the observed spread of actual against quoted duration over {len(ratios)} comparable orders, applied to this quote; not a statistical forecast",
    ), None


def estimate_arrival(
    quoted_production_weeks: ProductionRange,
    transit_weeks: WeekFact,
    approval_week: WeekFact | None = None,
    start: Literal["approval", "order"] = "approval",
    order_week: WeekFact | None = None,
    comparable_observations: list[ComparableObservation] | None = None,
) -> ArrivalResult:
    """Calculate on-site weeks for a vendor quote that starts at drawing approval (default) or at order placement.

    Transit follows production. All values use one project calendar. The output is a conditional
    quote range, not a vendor commitment. Comparable delivered orders, if at least five are given,
    add a reference range showing how far comparable orders slipped against their quotes; it is the
    observed spread, never a percentile estimate.
    """
    earliest = quoted_production_weeks.minimum + transit_weeks.value
    latest = quoted_production_weeks.maximum + transit_weeks.value
    sources = {"quoted_production_weeks": quoted_production_weeks.source, "transit_weeks": transit_weeks.source}
    reference, note = _reference(comparable_observations or [], earliest, latest, transit_weeks.value)
    if comparable_observations:
        sources["comparable_observations"] = "; ".join(sorted({o.source for o in comparable_observations}))[:300]
    anchor, anchor_name, status_needed = (approval_week, "approval_week", "needs_approval_date") if start == "approval" else (order_week, "order_week", "needs_order_date")
    common = dict(start=start, weeks_after_start=(earliest, latest), reference=reference, reference_note=note)
    after_approval = (earliest, latest) if start == "approval" else None
    if anchor is None:
        what = "approval" if start == "approval" else "order"
        return ArrivalResult(
            status=status_needed, weeks_after_approval=after_approval, onsite_week_range=None,
            reason=f"Request the {what} week to place this interval on the project schedule.", sources=sources, **common,
        )
    sources[anchor_name] = anchor.source
    base = anchor.value
    window = (base + earliest, base + latest)
    ref_window = (base + reference.weeks_after_start[0], base + reference.weeks_after_start[1]) if reference else None
    return ArrivalResult(
        status="conditional_on_quoted_terms", weeks_after_approval=after_approval, onsite_week_range=window,
        reason=f"{'Approval' if start == 'approval' else 'Order'} week plus quoted production duration plus transit; no other delays included.",
        sources=sources, reference_onsite_week_range=ref_window, **common,
    )
