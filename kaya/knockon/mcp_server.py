"""MCP server exposing the three KNOCK-ON tools. Every tool calls the same core as the UI and API.

Run over stdio (default):   python -m knockon.mcp_server
Run over HTTP:              python -m knockon.mcp_server --http --port 8808
"""
from __future__ import annotations

import argparse
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from . import core
from .schemas import CaseInput, DocumentInput

INSTRUCTIONS = (
    "KNOCK-ON pre-screens a substitute for data-center equipment (transformers first). "
    "Call compare_substitution to see what changed, screen_consequences to link each change to a project "
    "constraint, and decide_and_ask to learn how many project weeks the swap can actually recover. "
    "Each finding is labelled conclusive, cleared (that one constraint only), needs_engineer, not_stated or "
    "could_not_read, with page and quote evidence. KNOCK-ON never approves engineering; open items become "
    "questions for the vendor or the engineer of record. Pass package_dir, or documents, or a case_id from an earlier call."
)

mcp = FastMCP("knockon", instructions=INSTRUCTIONS)


def _input(
    case_id: Optional[str],
    package_dir: Optional[str],
    documents: Optional[list[dict[str, Any]]],
    revised_documents: Optional[list[dict[str, Any]]],
    project_facts: Optional[dict[str, Any]],
    recovery_target_weeks: Optional[float],
) -> CaseInput:
    return CaseInput(
        case_id=case_id,
        package_dir=package_dir,
        documents=[DocumentInput(**d) for d in (documents or [])],
        revised_documents=[DocumentInput(**d) for d in (revised_documents or [])],
        project_facts=project_facts,
        recovery_target_weeks=recovery_target_weeks,
    )


_DOC_HELP = (
    "documents: list of {role, path | text | content_base64, name?, revision?}. role is one of "
    "spec (buyer specification), original (baseline equipment documents), alternate (supplier submittal), "
    "logistics (delivery and room constraints), schedule (JSON project schedule)."
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


@mcp.tool(description=_DECIDE_AND_ASK_DOC + " " + _DOC_HELP)
def decide_and_ask(
    case_id: Optional[str] = None,
    package_dir: Optional[str] = None,
    documents: Optional[list[dict[str, Any]]] = None,
    revised_documents: Optional[list[dict[str, Any]]] = None,
    project_facts: Optional[dict[str, Any]] = None,
    recovery_target_weeks: Optional[float] = None,
) -> dict[str, Any]:
    res = core.decide_and_ask(_input(case_id, package_dir, documents, revised_documents, project_facts, recovery_target_weeks))
    return res.model_dump(mode="json")


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="knockon-mcp", description="KNOCK-ON MCP server")
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
