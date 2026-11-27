# Data and provenance

**Every sample document in this repository is synthetic.** Vendors ("Example Transformers Ltd (synthetic)", "Harbor Electric (synthetic)", and so on) and model numbers are fictional and labelled as such in each document. No confidential client data is used anywhere.

## How the samples were built

* `scripts/make_samples.py` (dev), `scripts/make_samples_milestone.py` (milestone) and `scripts/make_samples_final.py` (final) render text-based PDFs with ReportLab. Layout templates are in `scripts/templates_dev.py` and `scripts/templates_milestone.py`; the final set's documents are written inline in its script.
* Values are plausible, chosen by hand (for example a 2,500 kVA, 13.8 kV to 480Y/277 V liquid-filled transformer at 5.75 % impedance with a 5 % tolerance band). They are **not copied from any manufacturer datasheet or specification**.
* The lead-time context in the README (52–160 weeks) is background only and is never used as an input by the tools. It was gathered from public trade articles (for example https://www.industrialsage.com/switchgear-lead-times-2026/, https://www.gigaenergy.com/blog/lead-time-delays-for-data-centers and https://kaizen.com/us/insights-us/america-data-center-missing-dates/). Those figures were collected by a research pass and were not independently re-verified here; treat them as indicative.
* `labels.json` in each package states what each document really contains (field values, which findings should be raised, the expected decision). Labels are produced from the authored data, never from the extractor's output.

## Hold-out discipline (and where it falls short)

1. **dev**: used while building and tuning. Not a test.
2. **milestone**: two packages written after the dev layouts were frozen. The first run (before any change) is kept in `eval/results/milestone_first_run.json`. After that the extractor was generalised, so these packages stopped being unseen.
3. **final**: four packages written after the extractor was frozen at commit `b1a83d3`, run once. The run records whether the extraction and decision source files were byte-identical to that commit. The first-run result is kept in `eval/results/final.json` and was never overwritten.

Limits: the same people wrote the documents, the labels and the extractor, so none of this is independent. Real vendor documents will differ.

## Label corrections (disclosed)

**Milestone set.** After the first milestone run, three expected values in `m-02-meridian` were found to be my labelling errors and were corrected: `original.heat_loss_kw` (the original states a no-load and a load loss, whose sum, 13.7 kW, is a documented value), and `alternate.impedance_pct` and `alternate.shipping_total_weight_kg` (one page of that submittal is a scan, so by the scoring policy below a field not found elsewhere is `could_not_read`, not `not_stated`). The first-run file `eval/results/milestone_first_run.json` is scored against the labels as they were then.

**Final set.**

After the first final run, three expected values were found to be my labelling errors rather than extractor errors: `original.winding_config` in f-02, f-03 and f-04. Those original documents contain no vector-group line (only "Primary voltage 11 kV Delta"), so the extractor's `not_stated` was right. The labels were corrected, the same frozen code was re-scored (`eval/results/final_corrected_labels.json`), and the first scoring was kept. Each corrected label carries a `label_corrections` note.

One scoring policy worth knowing: if any page of a document is unreadable, a field not found on the readable pages is `could_not_read`, because it might be on the unreadable page. A label that expects `not_stated` in such a document is wrong by that rule.

## Public references

Typical impedance tolerances, NEC article numbers and the like are stated in the product only as context for drafted questions; nothing is looked up at run time and no external service is called by the default path.
