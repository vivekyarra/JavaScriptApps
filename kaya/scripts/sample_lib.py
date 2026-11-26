"""Helpers to render synthetic, text-based sample documents (PDF) and derive labels.

Everything generated here is synthetic. Vendors and models are fictional and labelled as such.
Labels are derived from the authored data below, never from the extractor.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STYLES = getSampleStyleSheet()


def build_pdf(path: Path, pages: list[list[tuple]], title: str = "synthetic sample") -> bytes:
    """pages: list of pages; each page a list of blocks: ('h', text) ('p', text) ('table', rows[, widths]) ('sp', h)."""
    story: list[Any] = []
    for i, blocks in enumerate(pages):
        for b in blocks:
            kind = b[0]
            if kind == "h":
                story.append(Paragraph(escape(b[1]), STYLES["Heading2"]))
            elif kind == "p":
                story.append(Paragraph(escape(b[1]), STYLES["BodyText"]))
            elif kind == "table":
                rows = [[escape(str(c)) for c in r] for r in b[1]]
                t = Table(rows, colWidths=b[2] if len(b) > 2 else None)
                t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(t)
            elif kind == "sp":
                story.append(Spacer(1, b[1]))
        if i < len(pages) - 1:
            story.append(PageBreak())
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=letter, title=title, author="synthetic", leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54).build(story)
    data = buf.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def build_pdf_with_scanned_pages(path: Path, pages: list[list[tuple]], scanned: set[int], title: str = "synthetic sample") -> None:
    """Render pages, then replace the given 1-based page numbers by image-only (scanned) pages."""
    import pdfplumber
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    tmp = path.with_suffix(".tmp.pdf")
    build_pdf(tmp, pages, title)
    images: dict[int, Any] = {}
    with pdfplumber.open(str(tmp)) as pdf:
        for n in scanned:
            images[n] = pdf.pages[n - 1].to_image(resolution=110).original
        count = len(pdf.pages)
        texts = {i + 1: p.extract_text() or "" for i, p in enumerate(pdf.pages)}
    # Rebuild: text pages are re-rendered individually so we can mix text and image pages.
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    base = PdfReader(str(tmp))
    for i in range(1, count + 1):
        if i in scanned:
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=letter)
            c.drawImage(ImageReader(images[i]), 0, 0, width=letter[0], height=letter[1])
            c.showPage()
            c.save()
            buf.seek(0)
            writer.add_page(PdfReader(buf).pages[0])
        else:
            writer.add_page(base.pages[i - 1])
    with open(path, "wb") as fh:
        writer.write(fh)
    tmp.unlink()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def truth_fields(data: dict[str, Any], absent_status: str = "not_stated", unreadable: Optional[set[str]] = None) -> dict[str, Any]:
    """Authoritative field truth for a rendered document, derived from the authored data dict."""
    unreadable = unreadable or set()
    out: dict[str, Any] = {}

    def put(name: str, present: bool, value: Any = None, **extra: Any) -> None:
        if name in unreadable:
            out[name] = {"status": "could_not_read"}
        elif present:
            out[name] = {"status": "documented", "value": value, **extra}
        else:
            out[name] = {"status": absent_status}

    put("rated_kva", "kva" in data, data.get("kva"))
    put("primary_voltage_v", "pri_v" in data, data.get("pri_v"))
    put("secondary_voltage_v", "sec_v" in data, data.get("sec_v"))
    put("impedance_pct", "z_pct" in data, data.get("z_pct"))
    put("xd_subtransient_pct", "xd_pct" in data, data.get("xd_pct"))
    put("winding_config", "family" in data, data.get("family"))
    dims = data.get("dims")
    put("dimensions_mm", dims is not None, sorted(dims) if dims else None)
    secs = data.get("sections")
    put("heaviest_transport_weight_kg", bool(secs), max(s[1] for s in secs) if secs else None)
    put("shipping_total_weight_kg", "ship_total_kg" in data, data.get("ship_total_kg"))
    put("total_weight_kg", "total_kg" in data, data.get("total_kg"))
    put("heat_loss_kw", "heat_kw" in data, data.get("heat_kw"))
    put("lead_time_weeks", "lead_max" in data, data.get("lead_max"))
    put("lead_time_start", data.get("start") is not None, data.get("start"))
    return out
