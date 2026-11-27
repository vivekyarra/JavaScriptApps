# Round 1 submission package

Everything the Devpost form asks for, in one place. Items in **[brackets]** are facts only the team can supply.

| Field | Entry |
| --- | --- |
| Track | **Track 03: Vertical Agents (Amber sub-agents)** |
| Challenge | A specialist Amber can call: *substitution decision* (what an alternate changes, which project constraint it hits, how many project weeks it can recover). It is not one of the listed specialists; it uses the lead-time and delivery-risk idea at the project milestone. |
| Division | **[Students / Professionals]**: students-only teams enter Students; a team with any working professional enters Professionals |
| Code repository | **[repository link]** (see "Repository" below) |
| README | `README.md` |
| Demo video (≤ 5 min) | `docs/media/pharos-demo.mp4`, 3 min 26 s, captioned. Upload it (for example to YouTube or Vimeo as unlisted) and paste the link: **[video link]**. Voice-over lines: `docs/VIDEO_NARRATION.md`. |
| Pitch deck (8 to 10 slides) | `docs/Pharos-pitch-deck.pptx` (10 slides). Slide 1 has a team placeholder to fill. |
| Team names and affiliations | **[names, college or company, for each of 2 to 4 members]** |
| Models used | **None on the default path.** Extraction is deterministic rules; arithmetic and decisions are code. An optional model gap-filler exists (`PHAROS_LLM_PROVIDER`, `PHAROS_LLM_MODEL`); it is implemented and unit-tested but **not benchmarked, so no accuracy, speed or cost is claimed for any model**. |
| Cost and response time per run | **$0** on the default path. Median **0.06 s** per tool call (max 0.12 s), 27 calls over the sample packages, on a 4-CPU Linux container, measured, including parsing five documents and database writes. |
| Data | Synthetic only; fictional vendors. How it was built and the corrections made: `docs/DATA.md`. No confidential client data. |
| IP terms | The organisers said IP terms would be shared before launch. **[confirm once published]** |

## Short description (for the project tagline)

When a vendor offers a faster alternate, Pharos tells the buyer how many of those weeks the project can actually use, what the substitute breaks, and what has to be true to get the time.

## Description

Data-center electrical equipment can take 52 to 160 weeks to arrive, so buyers accept substitutes every week. Document checkers flag the deviation ("5.00 % impedance instead of 5.75 %") but not what it does to the project. Pharos is a vertical agent: five specialists Amber can call independently over MCP, plus a recovery brief.

`check_submittal` tests a supplier submittal against the specification requirement by requirement (complies, deviates, missing, unreadable, conflicting) with both sides quoted from their pages. `find_alternatives` searches a library the buyer supplies and returns models that could meet the spec, or none; it never invents a product. `screen_consequences` links each documented change to a project constraint (freight elevator, floor loading, door, overhead clearance, cooling) and labels it conclusive, cleared (that one constraint only), needs engineer, not stated or could not read. `assess_delivery_risk` and `estimate_arrival` are deterministic calculators over sourced week numbers: they find the weeks the project can really recover across every PO line needed at the handoff, and an on-site range from a quoted production interval. `recovery_brief` assembles them into options, a ranking, a recommendation and drafted vendor and engineer questions. A revised vendor document updates the same decision and returns a diff.

The headline case: an alternate transformer ships 52 weeks earlier, but switchgear still controls energization, so the project can recover 2 weeks, not the 4 the buyer needs. Switchgear must be ready by week 78. The elevator limit blocks the route, so even the 2 weeks is potential recovery, not a promise.

It is a pre-screen. It never approves engineering, issues no electrical clearance or arc-flash numbers, invents no costs, and says "could not read" rather than guessing.

## How it meets the shared requirements

| Requirement | Where |
| --- | --- |
| Structured output (JSON) | all tools; schemas in `schemas/` |
| Callable by another agent (MCP) | `python -m pharos.server` (stdio or `--http`); `examples/mcp_client_demo.py` |
| Shows sources for every answer | document, revision, page and verbatim quote on every value; click through to the page in the workbench |
| Confidence and human hand-off | confidence per finding; open items become drafted questions for the vendor or the engineer of record |
| Never makes things up | quotes verified against the page text; costs only from a cited quote; missing values requested, not assumed; no electrical clearance |
| Easy to run | `./run.sh`; README; fresh-clone tested |
| Models, cost, response time | table above |
| Long-running plans and memory | immutable document revisions and numbered decision versions in SQLite; a revised document updates the same case |
| Document understanding | text-based PDFs: units in table headers, imperial and SI, per-unit, letter-labelled dimensions, scanned pages flagged |
| Linking records | the same equipment matched across spec, original and alternate; project constraints matched to findings |

## Honest limits to state if asked

* Evaluated on synthetic documents written by the same people who wrote the extractor. First-run results were poor on unfamiliar layouts (milestone findings 2/11; final fields 125/144, findings 7/16); the exposed gaps were fixed and are regression tests. Full record: `docs/EVAL.md`.
* No practising power-systems engineer has reviewed any case. The electrical output is a review request by design.
* Round 1 covers text-based transformer documents (generator sets are exercised in the samples). No OCR.
* The optional model path is not benchmarked.

## Repository

The code was built in this folder. The repository linked in the brief (`kittu181707/kaya`) refused the automated push (HTTP 403: the Claude GitHub App has no access to it), and the first commit and licence there belong to another person. A backup is on `vivekyarra/JavaScriptApps`, branch `claude/wonderful-cannon-z8cnd0`, folder `kaya/`. To publish: copy that folder's contents into the repository you submit and push as yourself. Before submitting, check that the repository is public (or shared with the organisers) and that `LICENSE` matches who owns it.

## Final checklist

- [ ] Fill the **[brackets]** above and on deck slide 1.
- [ ] Upload the video and paste its link.
- [ ] Confirm the division with every team member's status.
- [ ] Push the code to the repository you will submit; make sure it is reachable by the judges.
- [ ] Fresh-clone test: `./run.sh`, then `pytest` and `python examples/mcp_client_demo.py`.
- [ ] Submit early; Round 1 closes Sunday Dec 6, 2026 (11:45 p.m. IST per the organisers' dates).
