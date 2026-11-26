# Pitch outline (10 slides)

1. **KNOCK-ON.** "The vendor says 52 weeks faster. KNOCK-ON tells the buyer how many of those weeks the project can actually use, and what has to be true to get them." Track 03, Vertical Agents.
2. **The problem.** Switchgear and transformers take 52–160 weeks, so buyers accept alternates every week. Today a deviation is flagged but its consequences and its effect on the milestone are not.
3. **The question.** "We need to recover N weeks. Will this substitute do it, and what else has to be true?" Who asks: the procurement or package manager. Amber calls it when an alternate appears.
4. **Three callable tools.** `compare_substitution`, `screen_consequences`, `decide_and_ask`: structured JSON, page-and-quote evidence, the same core behind MCP, API and UI.
5. **One finding vocabulary.** conclusive / cleared (one constraint only) / needs engineer / not stated / could not read. No "approved", ever.
6. **The demo case.** 52 weeks earlier on paper, 2 weeks at the milestone, because switchgear controls. The elevator limit blocks the route. Next call: the switchgear vendor.
7. **Trust.** Every number cites page and quote; a quote not found on the page is dropped; no electrical clearance, no invented costs; "not stated" and "could not read" are different questions.
8. **Unfamiliar inputs and revisions.** A scanned page, a layout never seen, a revised vendor reply that changes the same decision and shows what changed.
9. **Honest evaluation.** First-run results on unfamiliar documents (milestone findings 2/11; final fields 125/144, findings 7/16), what broke, the generic fixes, the regression tests. Self-authored synthetic data, no engineer review yet.
10. **Build quality and next steps.** Default path needs no model: $0 and about 0.05 s per call; 74 tests; one-command setup. Round 2: engineer-checked electrical method, OCR with citations, nameplate-at-delivery check against accepted conditions (Track 02 bridge).
