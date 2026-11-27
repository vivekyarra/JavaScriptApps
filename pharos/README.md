# Pharos

**A recovery-plan pre-screen for equipment substitutions.** When a vendor offers a faster transformer or switchgear lineup, the buyer needs to know four things:
does the submittal actually meet the spec, what else could replace it, what does the swap break on this site, and how many project weeks can really be recovered once
*every* line needed at the handoff is counted. Pharos answers each as its own MCP tool, with page and quote evidence, and then assembles a recovery brief.

It is a pre-screen. It never approves engineering, issues no electrical clearance or arc-flash figure, invents no vendor, price or date, and says "could not read"
rather than guess. The default path calls no model and needs no network or API key, so it can be deployed privately.

## Five specialists on one MCP server

| Tool | Answers | Needs |
|---|---|---|
| `check_submittal` | Requirement by requirement: complies / deviates / missing / unreadable / conflicting, spec and submittal quoted side by side | spec + submittal documents |
| `find_alternatives` | Which models in a library **you supply** could meet the spec: supported / needs_confirmation / falls_short, or `none_supported` | spec + library (PDF, TXT, CSV) |
| `screen_consequences` | What each documented change does to a project constraint (elevator, floor, door, clearance, cooling): conclusive / cleared (that one constraint only) / needs_engineer / not_stated / could_not_read | documents + logistics |
| `assess_delivery_risk` | Weeks recovered at the shared handoff across all PO lines, who controls, float and margin, what must be ready by when | sourced week numbers |
| `estimate_arrival` | An on-site week range from a quoted production interval plus transit (quote bounds, never percentiles) | sourced week numbers |

`recovery_brief` runs the document path end to end: options (substitute / expedite / combined) compared at the same milestone with sourced costs only,
PO lines ranked by effect, a recommendation, and drafted questions for the vendor and the engineer of record. `compare_substitution` and `check_elevator_load` are also exposed.

**Worked example.** Transformer baseline week 82, alternate week 30, switchgear week 80, buyer needs 4 weeks: only **2** are recoverable and switchgear must be ready by
**week 78**. If switchgear is week 85 it controls both schedules and the swap gains **zero**.

## Run

```sh
uv sync --locked
uv run --locked python -m pharos.server            # MCP over stdio
uv run --locked python -m pharos.server --http --port 8808
uv run --locked pharos-api                          # web workbench + API on :8000
```

MCP client configuration (replace the directory):

```json
{"mcpServers": {"pharos": {"command": "uv", "args": ["--directory", "/path/to/pharos", "run", "--locked", "python", "-m", "pharos.server"]}}}
```

Try it on the bundled synthetic packages: `package_dir: "samples/milestone/m-01-harbor"`. `examples/mcp_client_demo.py` is a complete client.

## Evidence and honesty

- Every value carries document, revision, page and a verbatim quote that is checked against the page. A page that cannot be read is never reported as "not stated".
- Multi-model catalogue tables use the offered model's column or are withheld; a number is never taken from a neighbouring row.
- **Blind evaluation** (`docs/BLIND_EVAL.md`): 27 scenarios written by an independent author who never saw the code. **First run, frozen code: 5/27 scenarios, 72/135 items.**
  After fixing the layout and unit gaps it exposed: 21/27, 127/135, but that second score is **not** blind because the fixes were tuned on the same set. The six remaining
  failures are explained there, one by one. First-run result files are kept.
- Earlier synthetic dev, milestone and final sets and their label corrections: `docs/EVAL.md`.
- Public real documents (14 vendor and specification PDFs) are used only for invariants; see `scripts/fetch_public_docs.py` (hashes, URLs, access dates; PDFs not committed).
- Documents in the samples are synthetic with fictional vendors. No confidential data.

## The calculators (no documents needed)

**`assess_delivery_risk`** ranks PO lines required together at one handoff and compares the current schedule with a vendor revision or proposed substitution. Example arguments (illustrative references):

```json
{
  "po_lines": [
    {
      "line_id": "transformer",
      "baseline": {"week": 82, "source": "PO-17 rev A, line 1"},
      "proposed": {
        "week": 30,
        "source": "Substitution quote rev B, page 2",
        "open_conditions": [{"description": "Confirm transport route", "source": "Logistics register, item 4"}]
      }
    },
    {"line_id": "switchgear", "baseline": {"week": 80, "source": "PO-25 rev C, line 3"}}
  ],
  "post_handoff_weeks": {"value": 2, "source": "Schedule, install and test activity 9"},
  "recovery_target_weeks": {"value": 4, "source": "Package manager's recovery brief, page 1"}
}
```

On the supplied dates, baseline completion is **week 84** (`max(82, 80) + 2`). The proposed completion is **conditionally week 82** (`max(30, 80) + 2`). Potential recovery is **two weeks**, so the four-week target is `not_met` even if the route is confirmed. The proposed ranking puts switchgear first with action `seek_earlier_date`: both items would have to be ready by **week 78**. The transformer still has a separate `resolve_condition` action. Change the switchgear baseline to week 85 and it controls both schedules: potential recovery becomes **zero**.

- **Inputs:** use unique PO-line IDs, nonnegative whole readiness weeks with the same origin, and the same fixed post-handoff duration in both scenarios. Readiness means ready at the handoff, not shipped. Include only lines required at this joint handoff. This is not a general multi-stage critical-path engine.
- **Revisions:** omit `proposed` for unchanged lines. To withdraw a date, supply a proposed record with `week: null` and its source. A proposed record replaces the whole baseline readiness record for that line: include conditions that still apply. With no revisions the tool returns baseline triage only.
- **Slack and actions:** `float_to_handoff_weeks` is how far a line can slip before the scenario handoff moves. `margin_to_deadline_weeks` is relative to the earlier of an optional `required_handoff_week` and the handoff needed for the recovery target. Negative margin calls for an earlier date, even on a line with positive float. `keep_order` is a schedule-only recommendation. For example, with a week-82 handoff, a change from week 70 to 75 is five weeks late versus the prior promise but still has seven weeks of slack.
- **Uncertainty and ties:** undated lines are listed first for follow-up; an incomplete scenario has no milestone or controlling-line claim. Known dates are ordered latest first, with all ties retained and IDs breaking display ties. Open conditions make calculated dates conditional. If the baseline itself is uncertain, any computed delta is a what-if comparison and the recovery-target verdict is `needs_data`. A recovery target compares the two milestones, independently of the absolute need-by date. Negative recovery means the revision makes completion later.

**`check_elevator_load`** compares a single lift with its documented payload limit in kilograms. Example arguments (illustrative references):

```json
{
  "section_kg": {"value": 2100, "source": "Packing list rev B, row 2"},
  "limit_kg": {"value": 3600, "source": "Logistics plan rev A, page 3"}
}
```

This returns `needs_data`: section weight alone cannot clear the lift. Supply `additional_load_kg` for **all** other payload, or `documented_gross_kg` for the **entire** lift. A known overweight section fails even without rigging data. A documented gross is never added to rigging again. Conflicting totals return `needs_review`. A result of `within_weight_limit` concerns only this weight comparison, not route or installation approval.

**`estimate_arrival`** evaluates a vendor-quoted production interval starting at drawing approval, followed by transit. Example arguments:

```json
{
  "quoted_production_weeks": {"minimum": 22, "maximum": 24, "source": "Quote rev C, page 2"},
  "transit_weeks": {"value": 2, "source": "Freight terms, row 1"},
  "approval_week": {"value": 6, "source": "Schedule rev A, row 17"}
}
```

The structured result gives **24–26 weeks after approval**, or **project weeks 30–32** on this calendar. Omit `approval_week` when it is unknown: the relative interval remains valid, `onsite_week_range` is null and the result requests the approval date. All weeks are nonnegative whole weeks with one origin. These are conditional quote bounds, not historical forecasts or committed delivery dates.

## Verify

```sh
uv run --locked pytest -q                      # unit, interface, MCP (including offline) and regression tests
uv run --locked python -m unittest discover -s tests -v   # the calculators' original fixtures
uv run --locked pharos-blind --label rerun     # score the blind set (first-run file is never overwritten)
```

The calculators' fixtures in `tests/fixtures/pharos_development_cases.json` are development checks, not blind results.

## Layout

`pharos/` core (ingest, tables, extract, compare, discovery, screen, schedule, checks, decide, server, api) · `ui/` React workbench · `samples/` synthetic packages ·
`blind/` independently authored scenarios · `docs/` data, evaluation, submission notes · `schemas/` JSON Schemas for tool outputs.
