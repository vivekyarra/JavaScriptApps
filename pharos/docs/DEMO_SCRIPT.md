# Demo script (5 minutes)

Run `./run.sh`, open http://127.0.0.1:8000. Every number below is what the tool returns for the bundled synthetic packages; none is typed in.

**0:00 – Problem (30 s).** "A vendor offers an alternate transformer 52 weeks faster. The buyer needs the project to recover four weeks. The document checkers say 'deviates by 0.75 % impedance'. They do not say what it changes or whether it moves the energization date." Pitch line on screen: *The vendor says 52 weeks faster. Pharos tells the buyer how many of those weeks the project can actually use, and what has to be true to get them.*

**0:30 – The answer (60 s).** Pick `dev-01-oakridge`. Read the headline aloud: *No, not from the transformer swap alone … the most this swap can recover is 2 weeks … To recover 4 weeks, Main switchgear SWGR-1 must also be ready by week 78. With the elevator route blocked and no dated alternative, 2 weeks is potential recovery, not a promised saving.* Point at "Call next: Switchgear vendor" and the four stat tiles (82 baseline, 52 earlier, 2 recoverable, switchgear controls).

**1:30 – Findings with evidence (60 s).** Findings tab.
* Open the **Conclusive** finding: requirement on the left (freight elevator 3,600 kg, from the logistics page), supplier support on the right (4,100 kg, alternate p.1, rev A). Click "open page 1": the source page opens with the line highlighted.
* **Needs engineer**: impedance 5.75 % → 5.00 %. "Pharos issues no electrical clearance." Read the drafted engineer question.
* **Not stated**: heat loss. Vendor request drafted.

**2:30 – Compare (30 s).** Compare tab: documented vs not stated per field, changes highlighted, nothing invented.

**3:00 – Revised document (60 s).** History tab → *Apply the sample's revision "B"* (vendor splits the load into two sections). Show the diff: elevator finding **conclusive → cleared**, impedance and heat **still open**, milestone **did not move**. Overview: change the target to 2 and press Ask: *Only if…* (open items now listed as conditions).

**4:00 – An unfamiliar package (45 s).** Pick `m-02-meridian`: one page is a scan. Weights, losses and impedance are **could not read** (a different follow-up from *not stated*). Apply revision 3 (readable copy): the findings clear and the answer becomes **Yes**.

**4:45 – Agent interface and honesty (15 s).** In a terminal: `python examples/mcp_client_demo.py` returns the same decision over MCP. Close on: synthetic data, no electrical clearance, first-run evaluation numbers in the README.
