"""Document ingestion: text extraction with per-page read status.

Round 1 supports text-based PDFs, plain text/markdown and JSON. Pages with no usable text layer
(for example scanned images) are marked unreadable instead of being guessed at.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .schemas import DocumentInput, DocumentRef

MIN_ALPHA_CHARS = 20
MIN_READABLE_RATIO = 0.60


class Page(BaseModel):
    number: int
    text: str
    status: str = "ok"  # ok | unreadable
    reason: Optional[str] = None


class ParsedDocument(BaseModel):
    role: str
    name: str
    revision: Optional[str] = None
    sha256: str
    kind: str
    pages: list[Page]
    data: Any = None  # parsed JSON for schedule documents
    text_revision: Optional[str] = None
    parse_error: Optional[str] = None
    raw_b64: Optional[str] = Field(default=None, exclude=True)

    def ref(self) -> DocumentRef:
        return DocumentRef(
            role=self.role,
            name=self.name,
            revision=self.revision or self.text_revision,
            sha256=self.sha256,
            pages=len(self.pages),
            unreadable_pages=[p.number for p in self.pages if p.status != "ok"],
            kind=self.kind,
        )

    @property
    def effective_revision(self) -> Optional[str]:
        return self.revision or self.text_revision


_REV_RE = re.compile(r"\b(?:rev(?:ision)?\.?)\s*[:#]?\s*([A-Za-z0-9]{1,3})\b", re.I)


def detect_revision(first_page_text: str) -> Optional[str]:
    for line in first_page_text.splitlines()[:25]:
        m = _REV_RE.search(line)
        if m and m.group(1).lower() not in {"iew", "ise", "erse"}:
            return m.group(1).upper()
    return None


def _page_quality(text: str, has_images: bool) -> tuple[str, Optional[str]]:
    stripped = text.strip()
    alpha = sum(ch.isalpha() for ch in stripped)
    if alpha < MIN_ALPHA_CHARS:
        reason = "no text layer (image-only or scanned page)" if has_images or not stripped else "almost no text"
        return "unreadable", reason
    visible = [ch for ch in stripped if not ch.isspace()]
    good = sum(ch.isalnum() or ch in ".,:;()%/+-–—±°×x#&'\"@=<>[]" for ch in visible)
    if visible and good / len(visible) < MIN_READABLE_RATIO or "(cid:" in stripped:
        return "unreadable", "text layer is garbled"
    return "ok", None


def _parse_pdf(data: bytes) -> list[Page]:
    import pdfplumber

    pages: list[Page] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # pragma: no cover - defensive
                pages.append(Page(number=i, text="", status="unreadable", reason=f"extraction failed: {exc}"))
                continue
            status, reason = _page_quality(text, bool(page.images))
            pages.append(Page(number=i, text=text, status=status, reason=reason))
    return pages


def parse_bytes(name: str, data: bytes, role: str, revision: Optional[str] = None) -> ParsedDocument:
    sha = hashlib.sha256(data).hexdigest()
    suffix = Path(name).suffix.lower()
    pages: list[Page] = []
    kind = "text"
    parsed: Any = None
    err: Optional[str] = None
    if data[:5] == b"%PDF-" or suffix == ".pdf":
        kind = "pdf"
        try:
            pages = _parse_pdf(data)
        except Exception as exc:
            err = f"could not open PDF: {exc}"
            pages = [Page(number=1, text="", status="unreadable", reason=err)]
    elif suffix == ".json" or role == "schedule":
        kind = "json"
        try:
            parsed = json.loads(data.decode("utf-8"))
            pages = [Page(number=1, text=json.dumps(parsed, indent=1)[:2000], status="ok")]
        except Exception as exc:
            err = f"invalid JSON: {exc}"
            pages = [Page(number=1, text="", status="unreadable", reason=err)]
    else:
        text = data.decode("utf-8", errors="replace")
        chunks = text.split("\f") if "\f" in text else [text]
        for i, chunk in enumerate(chunks, start=1):
            status, reason = _page_quality(chunk, False)
            pages.append(Page(number=i, text=chunk, status=status, reason=reason))
    doc = ParsedDocument(role=role, name=name, revision=revision, sha256=sha, kind=kind, pages=pages, data=parsed, parse_error=err)
    if pages and pages[0].status == "ok" and kind != "json":
        doc.text_revision = detect_revision(pages[0].text)
    doc.raw_b64 = base64.b64encode(data).decode("ascii")
    return doc


def load_document(inp: DocumentInput, base_dir: Optional[Path] = None) -> ParsedDocument:
    if inp.path:
        p = Path(inp.path)
        if not p.is_absolute() and base_dir is not None:
            p = base_dir / p
        data = p.read_bytes()
        name = inp.name or p.name
    elif inp.content_base64:
        data = base64.b64decode(inp.content_base64)
        name = inp.name or f"{inp.role}.bin"
    elif inp.text is not None:
        data = inp.text.encode("utf-8")
        name = inp.name or f"{inp.role}.txt"
    else:
        raise ValueError(f"document for role '{inp.role}' needs path, text or content_base64")
    return parse_bytes(name, data, inp.role, inp.revision)
