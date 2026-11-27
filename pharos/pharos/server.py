"""The Pharos MCP server: five independently callable specialists plus a recovery brief, on one server.

Document tools (check_submittal, find_alternatives, screen_consequences, compare_substitution, recovery_brief)
read files and cite page and quote. Calculation tools (assess_delivery_risk, estimate_arrival, check_elevator_load)
take sourced numbers and need no documents. All call the same core as the API and the workbench.

Run over stdio (default):   python -m pharos.server
Run over HTTP:              python -m pharos.server --http --port 8808
No network is needed at run time; it can be deployed privately.
"""
from __future__ import annotations

import argparse
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from . import core
from .checks import check_elevator_load, estimate_arrival
from .schedule import assess_delivery_risk
from .schemas import CaseInput, DocumentInput

INSTRUCTIONS = (
    "Pharos is a recovery-plan pre-screen for equipment substitutions (transformers and switchgear first). Five specialists, each callable alone: "
    "check_submittal (does a supplier submittal meet the buyer spec, requirement by requirement), "
    "find_alternatives (which models in a library the caller supplies could meet the spec), "
    "screen_consequences (what each documented change does to a project constraint), "
    "assess_delivery_risk (how many project weeks a changed date really recovers, across every PO line needed together), "
    "estimate_arrival (a sourced on-site week range from a quote, never a percentile). "
    "recovery_brief runs the document path end to end and returns options, ranking, recommendation and drafted questions. "
    "Every finding is labelled conclusive, cleared (that one constraint only), needs_engineer, not_stated or could_not_read with page and quote evidence. "
    "Pharos never approves engineering and never invents a vendor, a price or a date; open items become questions."
)

mcp = FastMCP("Pharos", instructions=INSTRUCTIONS)
mcp.add_tool(assess_delivery_risk, structured_output=True)
mcp.add_tool(estimate_arrival, structured_output=True)
mcp.add_tool(check_elevator_load, structured_output=True)


def _input(
    case_id: Optional[str],
    package_dir: Optional[str],
    documents: Optional[list[dict[str, Any]]],
    revised_documents: Optional[list[dict[str, Any]]],
    project_facts: Optional[dict[str, Any]],
    recovery_target_weeks: Optional[float],
    library_dir: Optional[str] = None,
    offered_model: Optional[str] = None,
) -> CaseInput:
    return CaseInput(
        case_id=case_id,
        package_dir=package_dir,
        documents=[DocumentInput(**d) for d in (documents or [])],
        revised_documents=[DocumentInput(**d) for d in (revised_documents or [])],
        project_facts=project_facts,
        recovery_target_weeks=recovery_target_weeks,
        library_dir=library_dir,
        offered_model=offered_model,
    )


_DOC_HELP = (
    "documents: list of {role, path | text | content_base64, name?, revision?}. role is one of "
    "spec (buyer specification), original (baseline equipment documents), alternate (supplier submittal), "
    "logistics (delivery and room constraints), schedule (JSON project schedule), library (datasheet or CSV catalogue to search)."
)

_COMPARE_SUBSTITUTION_DOC = (
    "Compare the buyer's spec, the original equipment documents and the alternate submittal.\n\n    Returns, for a defined set of transformer/generator fields, each value with model, revision, page, quote and\n    units, marks every field documented / not_stated / could_not_read / conflicting, lists documented differences\n    (changed vs original, deviates from spec), and lists what the supplier never supplied."
)

_SCREEN_CONSEQUENCES_DOC = (
    'Link each documented change to a specific project constraint and label it.\n\n    Physical checks: heaviest shipping section vs freight elevator, weight per area vs floor limit, dimensions vs\n    door and overhead clearance, heat loss vs cooling allowance. Electrical: an impedance (or generator reactance)\n    change returns needs_engineer with a drafted question; no electrical clearance or arc-flash number is issued.\n    project_facts may supply constraints directly: elevator_capacity_kg, slab_limit_kg_m2, door_width_mm,\n    door_height_mm, ceiling_clearance_mm, cooling_capacity_kw.'
)

_DECIDE_AND_ASK_DOC = (
    "Answer the buyer's recovery target and prepare the questions.\n\n    Compares baseline and alternate dates at the same project milestone, names the controlling item, states the\n    maximum recoverable weeks and the conditions behind it, says what else must be ready to hit the target\n    (answer: yes / only_if / no_not_alone / no / needs_data), reports costs only when a quote or documented\n    estimate backs them, and returns drafted vendor, engineer and readable-copy questions. Pass revised_documents\n    with the same case_id to update the same decision; the result includes a diff against the previous version.\n    The schedule comes from a 'schedule' JSON document or project_facts['schedule']."
)


@mcp.tool(description=_COMPARE_SUBSTITUTION_DOC + " " + _DOC_HELP)
def compare_substitution(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    revised_documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    res = core.compare_substitution(_input(case_id, package_dir, documents, revised_documents, project_facts, None))
    return res.model_dump(mode="json")


@mcp.tool(description=_SCREEN_CONSEQUENCES_DOC + " " + _DOC_HELP)
def screen_consequences(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    revised_documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    res = core.screen_consequences(_input(case_id, package_dir, documents, revised_documents, project_facts, None))
    return res.model_dump(mode="json")


@mcp.tool(name="recovery_brief", description=_DECIDE_AND_ASK_DOC + " " + _DOC_HELP)
def recovery_brief(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    revised_documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
    recovery_target_weeks: Optional[float] = None,
) -> dict[str, Any]:
    res = core.decide_and_ask(_input(case_id, package_dir, documents, revised_documents, project_facts, recovery_target_weeks))
    return res.model_dump(mode="json")


_CHECK_SUBMITTAL_DOC = (
    "Check a supplier submittal against the buyer's specification, requirement by requirement.\n\n    Needs a 'spec' and an 'alternate' document. Each requirement returns complies / deviates / missing / unreadable / conflicting, "
    "with the requirement and the submittal value quoted from their pages. 'missing' says which pages were searched for what; an unreadable page is never reported as missing. "
    "offered_model selects the column when the submittal is a multi-model table."
)

_FIND_ALTERNATIVES_DOC = (
    "Search a library the caller supplies for models that could meet the buyer's requirements.\n\n    Needs a 'spec' document and library documents (role 'library', or library_dir with PDF/TXT/CSV files). "
    "Each candidate is checked with the same logic as check_submittal and cited on both sides. Returns supported / needs_confirmation / falls_short, ranked; "
    "none_supported is true when nothing in the library qualifies. A library listing is not stock, an offer or a certified equivalent, and nothing is ever generated."
)


@mcp.tool(description=_CHECK_SUBMITTAL_DOC + " " + _DOC_HELP)
def check_submittal(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    revised_documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
    offered_model: Optional[str] = None,
) -> dict[str, Any]:
    res = core.check_submittal(_input(case_id, package_dir, documents, revised_documents, project_facts, None, None, offered_model))
    return res.model_dump(mode="json")


@mcp.tool(description=_FIND_ALTERNATIVES_DOC + " " + _DOC_HELP)
def find_alternatives(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
    library_dir: Optional[str] = None,
    max_candidates: int = 10,
) -> dict[str, Any]:
    res = core.find_alternatives(_input(case_id, package_dir, documents, None, project_facts, None, library_dir), max_candidates=max_candidates)
    return res.model_dump(mode="json")


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="pharos-mcp", description="Pharos MCP server")
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8808)
    args = ap.parse_args(argv)
    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
