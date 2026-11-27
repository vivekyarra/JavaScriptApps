# Blind evaluation

**What it is.** 27 scenarios in 10 fictional packages (`blind/`), written and labelled by a separate author (an independent agent) who was
told the field names and decision semantics but never saw the Pharos source, tests or earlier results. 13 are `check_submittal`
(10 transformer, 3 switchgear), 8 are `decide`, 6 are `find_alternatives`. Layouts include wrong-column tables, models-in-rows catalogues,
Unit-column tables, EU number formats, short tons and lb, values only in notes, a conflicting submittal and an image-only page.

**How it was run.** Source tree clean at commit `a8e68f6`, scenarios committed, then one run with `pharos-blind`.
The result is `eval/results/blind-first-run.json` (the tool refuses to overwrite it).

## First run (frozen code)

| Kind | Scenarios fully correct | Labelled items correct |
|---|---|---|
| check_submittal | 1 / 13 | 47 / 95 |
| decide | 3 / 8 | 10 / 16 |
| find_alternatives | 1 / 6 | 15 / 24 |
| **Total** | **5 / 27** | **72 / 135** |

That is the honest blind number. It was poor.

## What the failures showed

- **Layouts, not logic.** Requirement tables with a Unit column; a Standard-design column beside the Offered one; catalogue tables with one
  model per row; wrapped table headers.
- **Number formats and units.** `1.600 kVA` / `6,0 %` (European), `4.9 short tons`.
- **Qualifiers on weights.** "maximum 3,100 kg" was compared as an exact match: two verdicts were right only by luck.
- **Tapping ranges** inside a voltage line were read as a ceiling.
- **find_alternatives** offered the buyer's own original model back, and could not read a model from a datasheet title.

## Fixes and the second score

Each fix is in git history after `a8e68f6`. Because they were made while looking at this set, **the after-fix score is not blind**.
It is a regression check (`tests/test_blind_regression.py`), kept as `eval/results/blind-after-fixes-3.json`.

| Kind | Scenarios fully correct | Labelled items correct |
|---|---|---|
| check_submittal | 12 / 13 | 93 / 95 |
| decide | 3 / 8 | 10 / 16 |
| find_alternatives | 6 / 6 | 24 / 24 |
| **Total** | **21 / 27** | **127 / 135** |

## Failures that remain (and why we did not "fix" them)

| Scenario | Disagreement | Our call |
|---|---|---|
| eskerhal-04 | Page 1 gives `1.600 kVA` and `20.000 V` with no decimal comma anywhere, so locale cannot be proven. | Refused to guess; reported "could not read reliably, confirm by hand". Conservative by design. |
| fenwick-01, kestrel-01 | Label says a section within the elevator limit clears the lift. | Pharos's rule: a section weight alone never clears an elevator; gross lift is required. We keep the rule and report `only_if`. The label author was not told of it. |
| fenwick-03, kestrel-04 | Label assumes crane-route remediation weeks are inside the route's ready date. | Pharos adds documented remediation weeks after the route is ready (conservative). Both readings are defensible; the label author flagged this as uncertain. |
| kestrel-03 | Label uses schedule keys (`expedite_arrival_week`) that are not part of the schedule format. | Out of contract; expedite options belong under `options` with a source. |

So of the six open scenarios, one is a deliberate refusal, three are semantic choices the author was not briefed on, and one is an out-of-contract
input. None is a hidden parsing error that we know of, but this is our reading; treat it as such.

## Limits

27 scenarios from one author is small. Documents are synthetic. Real public PDFs are checked only for invariants
(`tests/test_real_documents.py`: every documented value has a verified quote), not for accuracy. Re-author a fresh set before trusting any of these numbers.
