"""Build docs/Pharos-pitch-deck.pptx (10 slides). Needs: pip install python-pptx"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "docs" / "media"
INK, MUTED, ACCENT = RGBColor(0x16, 0x20, 0x2C), RGBColor(0x5B, 0x67, 0x76), RGBColor(0x1F, 0x4F, 0xD8)
RED, GREEN, AMBER, BLUE, GREY = RGBColor(0xB4, 0x23, 0x18), RGBColor(0x1A, 0x7F, 0x37), RGBColor(0x9A, 0x5B, 0x00), RGBColor(0x1F, 0x4F, 0xD8), RGBColor(0x4B, 0x55, 0x63)
PALE = RGBColor(0xF1, 0xF4, 0xF9)
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, s, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, "Calibri"
        p.space_after = Pt(6)
    return tb


def bullets(slide, x, y, w, h, items, size=18):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = "•  " + it
        r.font.size, r.font.color.rgb, r.font.name = Pt(size), INK, "Calibri"
        p.space_after = Pt(9)
    return tb


def box(slide, x, y, w, h, fill=PALE, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
    else:
        s.line.fill.background()
    s.adjustments[0] = 0.06
    s.shadow.inherit = False
    return s


def title(slide, s, sub=None):
    text(slide, 0.6, 0.35, 12.1, 0.9, s, 32, True)
    if sub:
        text(slide, 0.6, 1.1, 12.1, 0.5, sub, 16, False, MUTED)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.32), Inches(0.9), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()


def footer(slide, n):
    text(slide, 0.6, 7.05, 9, 0.3, "Pharos  |  Kaya AI Grand Challenge, Track 03", 10, False, MUTED)
    text(slide, 12.0, 7.05, 0.8, 0.3, str(n), 10, False, MUTED, PP_ALIGN.RIGHT)


def pic(slide, name, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    p = slide.shapes.add_picture(str(MEDIA / name), Inches(x), Inches(y), **kw)
    p.line.color.rgb = RGBColor(0xD9, 0xDE, 0xE5)
    return p


def chip(slide, x, y, w, label, color):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.42))
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background(); s.adjustments[0] = 0.5
    tf = s.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = RGBColor(255, 255, 255); r.font.name = "Calibri"


# 1 ---------------------------------------------------------------- title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height); bg.fill.solid(); bg.fill.fore_color.rgb = INK; bg.line.fill.background()
text(s, 0.9, 1.5, 11.5, 1.2, "Pharos", 66, True, RGBColor(255, 255, 255))
text(s, 0.9, 2.9, 11.5, 2.2, "The vendor says 52 weeks faster.\nPharos tells the buyer how many of those weeks the project can actually use, and what has to be true to get them.".split("\n"), 26, False, RGBColor(0xDD, 0xE6, 0xF5))
text(s, 0.9, 5.6, 11.5, 0.5, "Kaya AI Grand Challenge  |  Track 03: Vertical Agents  |  five MCP specialists Amber can call", 16, False, RGBColor(0x9D, 0xB8, 0xFF))
text(s, 0.9, 6.3, 11.5, 0.5, "Team: [names and affiliations]   Division: [Students / Professionals]", 14, False, RGBColor(0x9A, 0xA6, 0xB5))

# 2 ---------------------------------------------------------------- problem
s = prs.slides.add_slide(BLANK); title(s, "Buyers accept substitutes every week. Nobody can say what that costs the schedule.")
bullets(s, 0.6, 1.7, 7.2, 4.8, [
    "Switchgear and transformers can take 52 to 160 weeks to arrive (indicative figures from public trade articles).",
    "So when a vendor offers an alternate that ships sooner, the buyer is tempted to take it.",
    "Today the document is checked and a deviation is flagged: “5.00 % vs 5.75 % impedance”.",
    "No one answers the two questions that matter: what does this change on this project, and does it move the date?",
    "An alternate can ship 52 weeks earlier and recover 2, because another item controls the milestone.",
], 19)
box(s, 8.3, 1.8, 4.4, 4.3, PALE)
text(s, 8.6, 2.0, 3.8, 0.5, "The same offer, two readings", 16, True, ACCENT)
text(s, 8.6, 2.6, 3.8, 3.4, ["Document check:", "“Ships 52 weeks earlier. Deviates on impedance.”", "", "Pharos:", "“2 weeks at energization. Switchgear controls. The elevator blocks the route. To recover 4 weeks, switchgear must be ready by week 78.”"], 15)
footer(s, 2)

# 3 ---------------------------------------------------------------- question
s = prs.slides.add_slide(BLANK); title(s, "One question, asked by the buyer")
box(s, 0.6, 1.7, 12.1, 1.4, PALE)
text(s, 0.9, 1.85, 11.5, 1.2, "“We need to recover N weeks. Will this substitute do it, and what else has to be true?”", 26, True, ACCENT, anchor=MSO_ANCHOR.MIDDLE)
bullets(s, 0.6, 3.5, 6.0, 3.2, ["User: the procurement or package manager at a general contractor or data-center owner.", "Trigger: a vendor proposes an alternate, a submittal shows a deviation, or a lead time forces a swap.", "Amber calls Pharos as a specialist; it is also usable on its own."], 17)
bullets(s, 6.9, 3.5, 5.8, 3.2, ["Returns: the answer, the conditions behind it, what else must be ready, who to call next.", "Hands the engineer one precise question instead of a whole re-study request.", "A pre-screen. It never approves engineering."], 17)
footer(s, 3)

# 4 ---------------------------------------------------------------- how it works
s = prs.slides.add_slide(BLANK); title(s, "Five specialists, one server", "Each is callable alone. Structured JSON in and out; the UI, API and MCP server call the same core.")
for i, (name, desc) in enumerate([
    ("check_submittal", "Does the submittal meet the spec?\nRequirement by requirement: complies, deviates, missing, unreadable, conflicting. Both sides quoted."),
    ("find_alternatives", "What else could do it?\nSearches a library you supply. Supported, needs confirmation, falls short, or none supported. Never invents a product."),
    ("screen_consequences", "What does the change break here?\nElevator, floor, door, overhead, cooling. Impedance change goes to the engineer."),
    ("assess_delivery_risk", "How many weeks really recover?\nAll PO lines at one handoff. Who controls, float, margin, what must be ready by when."),
    ("estimate_arrival", "When does it land on site?\nQuoted production plus transit, as a sourced range. Never a percentile."),
]):
    x = 0.6 + i * 2.45
    box(s, x, 1.9, 2.3, 3.2, PALE)
    text(s, x + 0.12, 2.0, 2.1, 0.7, name, 14, True, ACCENT)
    text(s, x + 0.12, 2.75, 2.1, 2.3, desc.split("\n"), 12)
box(s, 0.6, 5.35, 12.1, 1.2, INK)
text(s, 0.9, 5.45, 11.5, 1.0, ["recovery_brief assembles them: options at the same milestone, PO lines ranked, a recommendation, drafted questions for vendor and engineer.", "Verified quotes | deterministic units and schedule logic | no model, no network on the default path: $0 per run, deployable privately."], 14, False, RGBColor(255, 255, 255), anchor=MSO_ANCHOR.MIDDLE)
footer(s, 4)

# 5 ---------------------------------------------------------------- labels
s = prs.slides.add_slide(BLANK); title(s, "One finding vocabulary. Never “approved”.")
rows = [("Conclusive", RED, "A documented value breaks a documented project constraint", "4,100 kg section vs a 3,600 kg freight elevator"),
        ("Cleared", GREEN, "A documented value meets that one constraint only", "2,100 kg section vs the same elevator; route still open"),
        ("Needs engineer", BLUE, "The change alters a study input", "Impedance 5.75 % to 5.00 %: protection and arc-flash studies"),
        ("Not stated", AMBER, "The readable submittal does not give the value", "No %Z anywhere: drafted vendor request"),
        ("Could not read", GREY, "The text could not be read reliably", "Scanned weights page: ask for a readable copy")]
for i, (lab, col, mean, ex) in enumerate(rows):
    y = 1.6 + i * 1.02
    chip(s, 0.6, y + 0.1, 2.2, lab, col)
    text(s, 3.0, y, 4.8, 0.9, mean, 16, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 7.9, y, 4.8, 0.9, ex, 14, False, MUTED, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 6.75, 12.1, 0.4, "“Not stated” and “could not read” get different follow-ups on purpose. No electrical clearance and no arc-flash numbers are issued.", 13, False, MUTED)
footer(s, 5)

# 6 ---------------------------------------------------------------- demo
s = prs.slides.add_slide(BLANK); title(s, "The demo case: 52 weeks on paper, 2 at the milestone")
pic(s, "overview.png", 0.5, 1.45, w=8.2)
bullets(s, 8.95, 1.6, 3.9, 5.2, ["Baseline transformer: week 82. Alternate: ships 52 weeks earlier.", "Switchgear is due in week 80, so it controls energization.", "Most the swap can recover: 2 weeks, against a 4-week target.", "To hit 4 weeks, switchgear must be ready by week 78. Call that vendor next.", "The elevator limit blocks the route, so 2 weeks is potential recovery, not a promised saving."], 15)
footer(s, 6)

# 7 ---------------------------------------------------------------- evidence
s = prs.slides.add_slide(BLANK); title(s, "Every finding shows its source")
pic(s, "evidence.png", 0.5, 1.45, w=8.2)
bullets(s, 8.95, 1.6, 3.9, 5.2, ["Requirement beside supplier support, each with document, revision, page and verbatim quote.", "Click through to the page; the line is highlighted.", "A quote that is not found on the page is dropped, never used.", "Missing values are requested, never invented. Costs appear only when a quote is cited.", "Cleared means that one constraint only."], 15)
footer(s, 7)

# 8 ---------------------------------------------------------------- revision + unreadable
s = prs.slides.add_slide(BLANK); title(s, "A revised vendor reply updates the same decision")
pic(s, "revision.png", 0.5, 1.5, w=6.2)
pic(s, "unreadable.png", 6.9, 1.5, w=6.2)
text(s, 0.5, 5.6, 6.2, 1.3, ["Revision B splits the load: the elevator finding goes conclusive to cleared, impedance and heat stay open, the milestone does not move. Both revisions are kept."], 14)
text(s, 6.9, 5.6, 6.2, 1.3, ["An unfamiliar package with a scanned page: weights, losses and impedance are “could not read”. A readable copy turns the answer into Yes."], 14)
footer(s, 8)

# 9 ---------------------------------------------------------------- evaluation
s = prs.slides.add_slide(BLANK); title(s, "Honest evaluation: a blind set we did not write", "27 scenarios, 10 packages, authored by an independent agent that never saw the code. First-run file kept.")
data = [("Run", "Scenarios fully correct", "Labelled items correct"),
        ("First run, code frozen", "5 / 27", "72 / 135"),
        ("After fixing what it exposed (not blind any more)", "21 / 27", "127 / 135")]
tbl = s.shapes.add_table(len(data), 3, Inches(0.6), Inches(1.8), Inches(12.1), Inches(1.8)).table
tbl.columns[0].width = Inches(6.1)
for c_ in range(1, 3): tbl.columns[c_].width = Inches(3.0)
for r, row in enumerate(data):
    for c_, val in enumerate(row):
        cell = tbl.cell(r, c_); cell.text = val
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(16); run.font.bold = (r == 0); run.font.name = "Calibri"
                run.font.color.rgb = RGBColor(255, 255, 255) if r == 0 else INK
        cell.fill.solid(); cell.fill.fore_color.rgb = INK if r == 0 else (PALE if r % 2 else RGBColor(255, 255, 255))
bullets(s, 0.6, 4.0, 12.1, 3.0, [
    "The first run was poor: layouts and units, not logic. Unit-column tables, a Standard column beside the Offered one, models-in-rows catalogues, European numbers, short tons.",
    "Six scenarios still fail: one refusal to guess a number locale, three semantic differences the author was not briefed on, one out-of-contract input. Each is explained in docs/BLIND_EVAL.md.",
    "Synthetic documents, one author. Real public PDFs are checked only for verified quotes. No engineer has reviewed these cases.",
], 15)
footer(s, 9)

# 10 --------------------------------------------------------------- build + next
s = prs.slides.add_slide(BLANK); title(s, "Build quality and what comes next")
for i, (n, l) in enumerate([("$0", "model cost per run on the default path"), ("5 + 1", "specialists plus the recovery brief"), ("176", "tests, including MCP with sockets disabled"), ("27", "blind scenarios, first run published")]):
    x = 0.6 + i * 3.05
    box(s, x, 1.6, 2.85, 1.7, PALE)
    text(s, x + 0.15, 1.7, 2.6, 0.8, n, 34, True, ACCENT)
    text(s, x + 0.15, 2.5, 2.6, 0.8, l, 13, False, MUTED)
bullets(s, 0.6, 3.7, 6.0, 3.2, ["Callable by Amber over MCP; JSON Schemas published.", "Structured output, page-and-quote sources, confidence, human hand-off.", "Optional model gap-filler: quote must verify verbatim; implemented and tested, not benchmarked."], 16)
text(s, 6.9, 3.65, 5.8, 0.4, "Round 2", 18, True, ACCENT)
bullets(s, 6.9, 4.15, 5.8, 2.8, ["Engineer-checked electrical method for the transformer terminal.", "OCR that keeps page citations for scanned submittals.", "Nameplate at delivery checked against the accepted conditions (Track 02 bridge).", "Generator and switchgear electrical rules."], 16)
footer(s, 10)

out = ROOT / "docs" / "Pharos-pitch-deck.pptx"
prs.save(out)
print("saved", out, "slides:", len(prs.slides))
