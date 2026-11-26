# Narration script for the demo video

`docs/media/knockon-demo.mp4` (3 min 8 s) is captioned, not voiced. These are the same lines with approximate start times if you want to record a voice-over. They are generated from `scripts/record_demo.js`, which also re-records the video.

| Time | Line |
| --- | --- |
| 0:00 | [Title card] The vendor says 52 weeks faster. KNOCK-ON tells the buyer how many of those weeks the project can actually use, and what has to be true to get them. |
| 0:09 | A vendor offers an alternate transformer 52 weeks faster. We need to recover 4 weeks. We load the project documents. |
| 0:13 | The answer: No, not from this swap alone. It ships 52 weeks earlier, but switchgear still controls energization. |
| 0:21 | Against the week-82 baseline the most it can recover is 2 weeks. To recover 4, switchgear must be ready by week 78. |
| 0:29 | The elevator route is blocked and has no dated alternative, so 2 weeks is potential recovery, not a promised saving. Next call: the switchgear vendor. |
| 0:38 | Findings. Each is labelled, never "approved". Conclusive: a documented value breaks a documented constraint. |
| 0:45 | Requirement on the left: freight elevator 3,600 kg. Supplier support on the right: 4,100 kg, alternate p.1, revision A. |
| 0:52 | Every quote opens its source page with the line highlighted. A quote that is not found on the page is dropped. |
| 1:00 | Needs engineer: impedance changed from 5.75 to 5.00 percent. KNOCK-ON issues no electrical clearance, only a precise question for the engineer of record. |
| 1:10 | Not stated: the supplier never gave heat loss. That becomes a drafted vendor request. |
| 1:16 | Compare: every field, per document, with status and confidence. Nothing is invented. |
| 1:23 | The clarification queue: drafted questions for the vendor and the engineer. Ticking one saves that it was sent. |
| 1:30 | The vendor replies with revision B: the load split into two lighter sections. We add it to the same case. |
| 1:35 | Same decision, version 2. The elevator finding goes from conclusive to cleared. Impedance and heat stay open. The milestone does not move. |
| 1:45 | Change the target to 2 weeks: now the answer is "Only if", and the open items are listed as conditions. |
| 1:53 | A different, unfamiliar package. One page of the supplier submittal is a scan. |
| 1:59 | Weights, losses and impedance are "could not read", not "not stated". Different problem, different follow-up: ask for a readable copy. |
| 2:08 | The vendor sends a readable copy. The findings clear, the impedance question disappears, and the diff shows exactly what changed. |
| 2:17 | The answer becomes Yes. |
| 2:22 | [MCP card] The same tools over MCP, the way Amber calls them (real output of examples/mcp_client_demo.py). |
| 2:39 | [Closing card] A pre-screen with cited evidence. It never approves engineering. No electrical clearance, no arc-flash numbers, no invented costs. Evaluated on synthetic documents we wrote ourselves; first-run results are in the repo, including what broke. Default path needs no model: $0 and about 0.05 s per call. |
