# KNOCK-ON

**The vendor says 52 weeks faster. KNOCK-ON tells the buyer how many of those weeks the project can actually use, and what has to be true to get them.**

Data-center equipment now takes 52–160 weeks to arrive, so buyers accept substitutes every week. KNOCK-ON takes the buyer's specification, the original equipment documents, the alternate supplier's submittal and the project's site limits and schedule, and answers three questions with page-and-quote evidence:

1. **What changed?** (`compare_substitution`)
2. **Which project constraint does each change hit?** (`screen_consequences`)
3. **Will this substitute recover the weeks we need, and what else has to be true?** (`decide_and_ask`)

It is a **pre-screen**. It never approves engineering: open items become drafted questions for the vendor or the engineer of record.

Built for the Kaya AI Grand Challenge, Track 03 (Vertical Agents). Round 1 scope: **text-based transformer documents** and a defined field set (generator sets are also exercised in the samples).

---

## Quick start

```bash
./run.sh            # creates .venv, installs, starts the workbench at http://127.0.0.1:8000
```

Or step by step:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m knockon.api            # workbench + API on :8000
python -m knockon.mcp_server     # MCP server on stdio (what an agent such as Amber connects to)
pytest                           # 75 tests
python -m knockon.evaluate --set dev
```

The UI is prebuilt in `ui/dist`. To rebuild it: `cd ui && npm install && npm run build` (Node 18+).

### Connect an agent (MCP)

```json
{ "mcpServers": { "knockon": { "command": "/path/to/kaya/.venv/bin/python", "args": ["-m", "knockon.mcp_server"], "cwd": "/path/to/kaya" } } }
```

HTTP transport: `python -m knockon.mcp_server --http --port 8808`. A runnable client demo is in [`examples/mcp_client_demo.py`](examples/mcp_client_demo.py).

---

## The three tools

All three take the same input and return structured JSON (schemas in [`schemas/`](schemas)). The UI, the HTTP API and the MCP server call exactly the same core functions in `knockon/core.py`; there is no demo-only path.

| Tool | Returns |
| --- | --- |
| `compare_substitution` | For a defined field set, the value in the specification, the original equipment documents and the alternate, each with document, revision, page, verbatim quote and units. Every field is `documented`, `not_stated`, `could_not_read` or `conflicting`. Lists documented differences (changed vs original, deviates from spec) and what the supplier never supplied. |
| `screen_consequences` | Each documented change linked to a project constraint and labelled (below). Physical: heaviest shipping section vs freight elevator, weight per area vs floor limit, dimensions vs door and overhead clearance, heat loss vs cooling allowance. Electrical: an impedance (or generator reactance) change returns *engineer review needed* with the question drafted. |
| `decide_and_ask` | Takes the recovery target (weeks). Compares baseline and alternate **at the same project milestone**, names the controlling item, and answers `yes` / `only_if` / `no_not_alone` / `no` / `needs_data`, with the conditions behind the answer, what else must be ready, who to call next, costs only when a quote is cited, and drafted vendor / engineer / readable-copy questions. A revised document updates the same decision and returns a diff. |

### Finding labels (never "approved")

| Label | Meaning | Example |
| --- | --- | --- |
| `conclusive` | A documented value breaks a documented project constraint | 4,100 kg section vs 3,600 kg freight elevator |
| `cleared` | A documented value meets **that one constraint only** | 2,100 kg section vs the same elevator; route and installation still checked separately |
| `needs_engineer` | The change alters a study input | impedance 5.75 % → 5.00 %: protection and arc-flash studies need review |
| `not_stated` | The readable submittal does not give the value | no %Z anywhere in the readable pages → drafted vendor request |
| `could_not_read` | The text could not be read reliably (scanned page, or a line that mentions the field but could not be parsed) | weights page is a scan → ask for a text-based copy |

`not_stated` and `could_not_read` get different follow-ups on purpose. If any page of a document is unreadable, a field not found elsewhere is reported as `could_not_read`, never `not_stated`.

### Example (the demo case)

```bash
python - <<'PY'
from knockon.core import decide_and_ask
from knockon.schemas import CaseInput
print(decide_and_ask(CaseInput(package_dir="samples/dev/dev-01-oakridge")).headline)
PY
```

> No, not from the transformer swap alone. The alternate ships 52 weeks earlier, but Main switchgear SWGR-1 is still due in week 80. Against the week-82 baseline, the most this swap can recover is 2 weeks, assuming the delivery route is resolved in time and installation and testing durations are unchanged. To recover 4 weeks, Main switchgear SWGR-1 must also be ready by week 78. With the elevator route blocked and no dated alternative, 2 weeks is potential recovery, not a promised saving.

---

## What it deliberately does not do

* **No electrical clearance and no arc-flash numbers.** A transformer-terminal estimate is not a verdict for a downstream panel, and an arc-flash calculation needs installed breaker settings and clearing times. An impedance change always returns `needs_engineer` with a drafted question. (An engineer-checked method is Round 2 work.)
* **No invented values.** Costs appear only when a quote or documented estimate is cited; missing impedance returns "request impedance data", never a tolerance band around a guess; unit-ambiguous weights ("tons") are not converted.
* **No scanned or CAD-only documents.** Pages without a text layer are flagged `could_not_read`; there is no OCR in Round 1.
* **No bid leveling** (Amber already does it) and no autonomous emails or purchase orders.
* **`cleared` is narrow.** A cleared weight does not clear the route; a cleared floor pressure is an average over the stated footprint only.

---

## Models, cost and speed

| | |
| --- | --- |
| **Default extraction** | Deterministic rules over the document text. **No model is called; cost per run is $0.** |
| **Arithmetic and decisions** | Plain code (unit conversion, schedule and milestone logic). Never a model. |
| **Optional model gap-filler** | `KNOCK-ON` can ask a model to propose values for fields the rules could not read. Enable with `KNOCKON_LLM_PROVIDER=anthropic\|openai`, `KNOCKON_LLM_MODEL=<model id>` and the provider's API key (`OPENAI_BASE_URL` points it at any OpenAI-compatible server, including a local model). A proposal is accepted only if its quote is found verbatim on the cited page **and** the number is written inside that quote; code does the unit conversion. This path is implemented and unit-tested with a fake client. **It has not been benchmarked here: no accuracy, latency or cost figure is claimed for any model.** |
| **Measured speed (default path)** | Median **0.05 s** per tool call, max 0.09 s, on a 4-CPU Linux container. This includes parsing five documents, extraction and database writes for a fresh case. Mean for running all three tools on one sample package: 0.13–0.19 s. |

---

## Evaluation (read this before trusting any number)

Details, process and every miss are in [`docs/EVAL.md`](docs/EVAL.md). Short version:

| Set | What it is | Fields | Findings | Decision checks | Revisions |
| --- | --- | --- | --- | --- | --- |
| dev (3 packages) | the extractor was tuned on these | 108/108 | 16/16 | 18/18 | 5/5 |
| milestone, **first run** (2 unfamiliar packages) | before any change | 58/72 | **2/11** | 12/12 | 7/10 |
| milestone, after generalisation | no longer unseen | 72/72 | 11/11 | 12/12 | 10/10 |
| final hold-out, **first run** (4 packages) | run once, extractor frozen and verified byte-identical | 125/144 | **7/16** | 14/19 | 2/2 |
| final, after correcting 3 of **my own label errors** | same frozen code | 128/144 | 7/16 | 14/19 | 2/2 |
| final, after fixing the gaps it exposed | **not a hold-out any more** | 144/144 | 15/16 | 19/19 | 2/2 |

What to take from this:

* **The decision logic held up on unfamiliar inputs; extraction did not generalise on the first try.** The failures were layout and phrasing gaps (units in table headers, "per cent", "wide by … high", a bullet glyph that made a whole page look unreadable). They were fixed generically and each is now a regression test.
* **Most misses fail safe, but not all.** In the first final run, 84 of 85 `documented` fields at confidence ≥ 0.8 were correct; the one wrong value was a conflict the parser did not notice, and the other misses were `could_not_read` / `not_stated`, which route to a person. **The milestone first run was worse: two voltages were confidently assigned to the wrong winding** (for example a number written before its "primary" label, or an "HV/LV" pair). That is the error that matters most; it was fixed with order-aware parsing and is covered by tests, but it shows the extractor can be confidently wrong on a layout it has not seen.
* **These are self-authored synthetic documents, written by the same people who wrote the extractor.** They are not independent, not representative of industry documents, and not evidence of production accuracy. Real vendor PDFs will contain layouts none of these cover. The honest claim is: what it reads, it reads with citations; what it cannot read, it says so.
* Nothing here is reviewed by a practising power-systems engineer.

Reproduce: `python -m knockon.evaluate --set dev|milestone` (the final set refuses a second run unless `--rerun-final`).

---

## Inputs

* `documents`: `[{role, path | text | content_base64, name?, revision?}]` with `role` one of `spec` (buyer specification), `original` (baseline equipment documents), `alternate` (supplier submittal), `logistics` (site limits), `schedule` (JSON). Or pass `package_dir` pointing at a folder with a `manifest.json` (see `samples/`).
* `project_facts`: site limits can be given directly: `elevator_capacity_kg`, `slab_limit_kg_m2`, `door_width_mm`, `door_height_mm`, `ceiling_clearance_mm`, `cooling_capacity_kw`, plus a `schedule` object.
* `recovery_target_weeks`: the weeks the buyer needs to recover.
* `case_id`: pass the id from an earlier call plus `revised_documents` to update the same decision.

Document and schedule formats: [`docs/INPUTS.md`](docs/INPUTS.md). Supported fields: kVA, primary and secondary voltage, %Z (or generator Xd″), winding configuration, overall dimensions, shipping sections and weights, total weight, heat loss, quoted lead time and its start condition. Text-based PDFs and `.txt` only.

---

## Repository layout

```
knockon/        core engine: ingest, extract, compare, screen, decide, store, core, MCP server, API, evaluation
ui/             React + TypeScript evidence workbench (prebuilt in ui/dist)
samples/        synthetic packages: dev/, milestone/, final/ (each with labels.json)
scripts/        sample generators and helpers
eval/results/   recorded evaluation runs (first runs are kept, not overwritten)
schemas/        JSON Schemas for tool input and output
tests/          75 tests (units, extraction, every decision branch, MCP, API, regressions)
docs/           EVAL.md, DATA.md, INPUTS.md, SUBMISSION.md, DEMO_SCRIPT.md, VIDEO_NARRATION.md, PITCH_OUTLINE.md, the deck and media/
```

State is stored in SQLite (`data/knockon.db`, override with `KNOCKON_DB`): every document revision is kept immutably and every decision is a numbered version with a diff against the previous one.

## Submission materials

* Pitch deck (10 slides): [`docs/KNOCK-ON-pitch-deck.pptx`](docs/KNOCK-ON-pitch-deck.pptx)
* Demo video (3 min 8 s, captioned): [`docs/media/knockon-demo.mp4`](docs/media/knockon-demo.mp4); voice-over lines in [`docs/VIDEO_NARRATION.md`](docs/VIDEO_NARRATION.md)
* Everything the Devpost form asks for, with the fields only the team can fill: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)

## Licence

MIT (see `LICENSE`).
