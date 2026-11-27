"""Real public documents (not committed): fetch with scripts/fetch_public_docs.py. Skipped when absent.

These are invariants, not accuracy claims: nothing crashes and every value Pharos reports as documented has a
quote that really appears on the cited page.
"""
import hashlib
import json
from pathlib import Path

import pytest

from pharos.extract import extract_document
from pharos.ingest import load_document
from pharos.schemas import DocumentInput

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "public_docs"
MANIFEST = json.loads((ROOT / "data" / "public_docs_manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("m", MANIFEST, ids=[m["file"] for m in MANIFEST])
def test_documented_values_have_verified_quotes(m):
    path = CACHE / m["file"]
    if not path.exists():
        pytest.skip("public document not fetched")
    if hashlib.sha256(path.read_bytes()).hexdigest() != m["sha256"]:
        pytest.skip("publisher revised this file since the manifest was written")
    doc = load_document(DocumentInput(role=m.get("role", "alternate"), path=str(path), name=m["file"]))
    fields = extract_document(doc)
    for name, fv in fields.items():
        if fv.status == "documented":
            assert fv.evidence, name
            assert all(e.verified for e in fv.evidence), (m["file"], name)
