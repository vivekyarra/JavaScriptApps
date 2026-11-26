"""Build docs/KNOCK-ON-pitch-deck.pptx (10 slides). Needs: pip install python-pptx"""
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
    text(slide, 0.6, 7.05, 9, 0.3, "KNOCK-ON  |  Kaya AI Grand Challenge, Track 03", 10, False, MUTED)
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
text(s, 0.9, 1.5, 11.5, 1.2, "KNOCK-ON", 66, True, RGBColor(255, 255, 255))
text(s, 0.9, 2.9, 11.5, 2.2, "The vendor says 52 weeks faster.\nKNOCK-ON tells the buyer how many of those weeks the project can actually use, and what has to be true to get them.".split("\n"), 26, False, RGBColor(0xDD, 0xE6, 0xF5))
text(s, 0.9, 5.6, 11.5, 0.5, "Kaya AI Grand Challenge  |  Track 03: Vertical Agents  |  three MCP tools Amber can call", 16, False, RGBColor(0x9D, 0xB8, 0xFF))
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
text(s, 8.6, 2.6, 3.8, 3.4, ["Document check:", "“Ships 52 weeks earlier. Deviates on impedance.”", "", "KNOCK-ON:", "“2 weeks at energization. Switchgear controls. The elevator blocks the route. To recover 4 weeks, switchgear must be ready by week 78.”"], 15)
footer(s, 2)

# 3 ---------------------------------------------------------------- question
s = prs.slides.add_slide(BLANK); title(s, "One question, asked by the buyer")
box(s, 0.6, 1.7, 12.1, 1.4, PALE)
text(s, 0.9, 1.85, 11.5, 1.2, "“We need to recover N weeks. Will this substitute do it, and what else has to be true?”", 26, True, ACCENT, anchor=MSO_ANCHOR.MIDDLE)
bullets(s, 0.6, 3.5, 6.0, 3.2, ["User: the procurement or package manager at a general contractor or data-center owner.", "Trigger: a vendor proposes an alternate, a submittal shows a deviation, or a lead time forces a swap.", "Amber calls KNOCK-ON as a specialist; it is also usable on its own."], 17)
bullets(s, 6.9, 3.5, 5.8, 3.2, ["Returns: the answer, the conditions behind it, what else must be ready, who to call next.", "Hands the engineer one precise question instead of a whole re-study request.", "A pre-screen. It never approves engineering."], 17)
footer(s, 3)

# 4 ---------------------------------------------------------------- how it works
s = prs.slides.add_slide(BLANK); title(s, "Three tools, one core", "Structured JSON in and out. The UI, the API and the MCP server call the same functions.")
for i, (name, desc) in enumerate([
    ("compare_substitution", "What changed?\nSpec vs original vs alternate, per field, with document, revision, page, quote and units. Documented, not stated, could not read, or conflicting."),
    ("screen_consequences", "Which constraint does each change hit?\nElevator, floor, door, overhead, cooling. Impedance change returns “engineer review needed”."),
    ("decide_and_ask", "Will it recover the weeks?\nCompares at the same milestone, names the controlling item, answers the target, drafts the questions."),
]):
    x = 0.6 + i * 4.1
    box(s, x, 1.9, 3.9, 3.0, PALE)
    text(s, x + 0.2, 2.0, 3.5, 0.5, name, 18, True, ACCENT)
    text(s, x + 0.2, 2.6, 3.5, 2.3, desc.split("\n"), 14)
    if i < 2:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 3.93), Inches(3.2), Inches(0.2), Inches(0.4)); a.fill.solid(); a.fill.fore_color.rgb = MUTED; a.line.fill.background()
box(s, 0.6, 5.3, 12.1, 1.2, INK)
text(s, 0.9, 5.4, 11.5, 1.0, ["Shared core  |  text extraction with verified quotes  |  deterministic unit conversion and schedule logic  |  SQLite: immutable revisions, numbered decisions, clarification records", "No model on the default path: cost per run is $0."], 15, False, RGBColor(255, 255, 255), anchor=MSO_ANCHOR.MIDDLE)
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
s = prs.slides.add_slide(BLANK); title(s, "Honest evaluation: first run on unfamiliar documents", "Self-authored synthetic packages; the first-run files are kept unedited in the repo.")
data = [("Set", "Fields", "Findings", "Decisions"),
        ("Milestone, first run (2 packages)", "58/72", "2/11", "12/12"),
        ("Final hold-out, first run (4 packages)", "125/144", "7/16", "14/19"),
        ("Final, after correcting my label errors", "128/144", "7/16", "14/19"),
        ("Final, after fixing what it exposed (no longer a hold-out)", "144/144", "15/16", "19/19")]
tbl = s.shapes.add_table(len(data), 4, Inches(0.6), Inches(1.8), Inches(12.1), Inches(2.6)).table
tbl.columns[0].width = Inches(6.1)
for c in range(1, 4): tbl.columns[c].width = Inches(2.0)
for r, row in enumerate(data):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c); cell.text = val
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(15); run.font.bold = (r == 0); run.font.name = "Calibri"
                run.font.color.rgb = RGBColor(255, 255, 255) if r == 0 else INK
        cell.fill.solid(); cell.fill.fore_color.rgb = INK if r == 0 else (PALE if r % 2 else RGBColor(255, 255, 255))
bullets(s, 0.6, 4.7, 12.1, 2.3, [
    "The decision logic held on unfamiliar inputs; extraction did not generalise on the first try: units in table headers, “per cent”, “wide by … high”, a bullet glyph that blanked a page.",
    "Most misses were abstentions that route to a person. Not all: the milestone first run read two voltages against the wrong winding. Fixed, and covered by tests.",
    "No engineer has reviewed these cases. Real vendor PDFs will differ.",
], 15)
footer(s, 9)

# 10 --------------------------------------------------------------- build + next
s = prs.slides.add_slide(BLANK); title(s, "Build quality and what comes next")
for i, (n, l) in enumerate([("$0", "model cost per run on the default path"), ("0.05 s", "median per tool call, 4 CPUs"), ("75", "tests: units, every decision branch, MCP, API"), ("1 command", "./run.sh from a fresh clone")]):
    x = 0.6 + i * 3.05
    box(s, x, 1.6, 2.85, 1.7, PALE)
    text(s, x + 0.15, 1.7, 2.6, 0.8, n, 34, True, ACCENT)
    text(s, x + 0.15, 2.5, 2.6, 0.8, l, 13, False, MUTED)
bullets(s, 0.6, 3.7, 6.0, 3.2, ["Callable by Amber over MCP; JSON Schemas published.", "Structured output, page-and-quote sources, confidence, human hand-off.", "Optional model gap-filler: quote must verify verbatim; implemented and tested, not benchmarked."], 16)
text(s, 6.9, 3.65, 5.8, 0.4, "Round 2", 18, True, ACCENT)
bullets(s, 6.9, 4.15, 5.8, 2.8, ["Engineer-checked electrical method for the transformer terminal.", "OCR that keeps page citations for scanned submittals.", "Nameplate at delivery checked against the accepted conditions (Track 02 bridge).", "Generator and switchgear electrical rules."], 16)
footer(s, 10)

out = ROOT / "docs" / "KNOCK-ON-pitch-deck.pptx"
prs.save(out)
print("saved", out, "slides:", len(prs.slides))
