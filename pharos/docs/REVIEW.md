# Independent code review

After the evaluation work, an independent reviewer (a separate model session, read-only, not told what to expect) was asked to find reproducible bugs in the decision, screening, extraction, persistence and API code. Findings I reproduced myself before changing anything are marked.

## Fixed, each with a regression test (`tests/test_review_fixes.py`)

| # | Bug | Severity | Fix |
| --- | --- | --- | --- |
| 1 | European number formats were silently misread: `7,5 t` read as 5,000 kg, `7.000,5 kg` as 5 kg, `2.500 kVA` as 2.5 kVA (reproduced) | high | numbers are strictly en-US; ambiguous forms are refused and the field becomes `could_not_read` |
| 2 | Lead time taken from the wrong clause: `Shipment time: 2 weeks transit; lead time 30 weeks ARO` read as 2 weeks; two clauses with different starts gave an inconsistent pair (reproduced) | high | clause-wise parsing, transit and installation times ignored, differing clauses become `conflicting` |
| 3 | Impedance read as 100 % (`at 100% load`), as 7.5 % (`Impedance tolerance: 7.5 %`) or as the low end of a range (reproduced) | high | load percentages, tolerance-as-subject and ranges are not read |
| 4 | Vector-group clock position ignored: `Dyn11` against `Dyn5` raised nothing | medium-high | same family with a different clock position now needs engineer review |
| 5 | A required schedule item with no arrival week was silently dropped, so the recoverable weeks were computed as if it did not exist | high | the answer becomes `needs_data` and names the item |
| 6 | API path guard used a string prefix, so a sibling folder `samples_evil` passed (reproduced) | medium | real path containment |
| 8 | The version diff hid changed details under an unchanged label, and `milestone_moved` ignored shifts that kept the difference equal | low-medium | an `updated` list (computed values or quoted evidence changed) and a fuller milestone comparison; a changed revision letter alone is not a change |
| 9 | Impossible targets gave nonsense (`must be ready by week -118`); a later alternate read "can recover -8 weeks" | low | impossible targets answer `no` with a clear reason, a negative target is rejected, delays are described as delays |
| 10 | An alternate equal to the original but outside the specification's tolerance band raised nothing | medium | flagged for engineer review |
| 12 | One alternate route resolved every physical blocker | medium | a route may list the findings it `resolves`; without a list it covers the physical route as documented |
| 13 | A missing order release week was silently taken as 0 | low | stated as a condition |

## Not changed (design decisions)

* **A reused `case_id` accumulates documents, facts and target** (reviewer item 7). This is how revisions work. It is now documented in `docs/INPUTS.md`; use a new `case_id` for a different job.
* **A door that passes only if the unit is laid on its side is `conclusive`** (item 11). The submittal does not say tilting is allowed, so upright is the documented basis; the finding text states that it would pass if tilted and the follow-up asks the vendor.
* `Total weight of oil: …` is classified as a total weight and produces a `conflicting` status (item 14). Safe but noisy.

The reviewer also checked and found correct: the milestone arithmetic for every answer branch including boundary equality, `requires: false`, remediation filtering, lead-time ranges, the kVA min/max logic, the slab/elevator/ceiling/heat boundaries, idempotence, and the `..` and symlink guards.
