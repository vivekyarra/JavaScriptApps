"""HTTP API for the evidence workbench. It calls exactly the same core functions as the MCP server."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import core
from .schemas import CaseInput, DocumentInput

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
UI_DIST = ROOT / "ui" / "dist"

app = FastAPI(title="KNOCK-ON", version="0.1.0", description="Substitution decision tools: workbench API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def _inside(path: Path, root: Path) -> bool:
    """True only if `path` is `root` or lies beneath it (a string prefix check would let a sibling like samples_evil through)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _allowed(path: str) -> bool:
    return _inside(Path(path), SAMPLES)


def _guard(inp: CaseInput) -> CaseInput:
    """The web API only reads files under samples/. Uploaded files arrive as bytes, never as paths."""
    if inp.package_dir and not _allowed(inp.package_dir):
        raise HTTPException(400, "package_dir must be inside the samples directory")
    for d in list(inp.documents) + list(inp.revised_documents):
        if d.path:
            base = Path(inp.package_dir) if inp.package_dir else None
            full = (base / d.path) if (base and not Path(d.path).is_absolute()) else Path(d.path)
            if not _allowed(str(full)):
                raise HTTPException(400, "document paths must be inside the samples directory; upload the file instead")
    return inp


def _err(exc: Exception) -> HTTPException:
    return HTTPException(400, str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "tools": ["compare_substitution", "screen_consequences", "decide_and_ask"]}


@app.get("/api/samples")
def samples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for set_dir in sorted(SAMPLES.iterdir() if SAMPLES.exists() else []):
        if not set_dir.is_dir():
            continue
        for pkg in sorted(set_dir.iterdir()):
            mf = pkg / "manifest.json"
            if not mf.exists():
                continue
            m = json.loads(mf.read_text(encoding="utf-8"))
            out.append({
                "id": f"{set_dir.name}/{pkg.name}", "set": set_dir.name, "name": pkg.name, "title": m.get("title"),
                "recovery_target_weeks": m.get("recovery_target_weeks"),
                "documents": [d["role"] for d in m.get("documents", [])],
                "revisions": [r["label"] for r in m.get("revisions", [])],
            })
    return out


@app.post("/api/tools/compare")
def tool_compare(inp: CaseInput) -> Any:
    try:
        return core.compare_substitution(_guard(inp)).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/tools/screen")
def tool_screen(inp: CaseInput) -> Any:
    try:
        return core.screen_consequences(_guard(inp)).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/tools/decide")
def tool_decide(inp: CaseInput) -> Any:
    try:
        return core.decide_and_ask(_guard(inp)).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/cases/from-sample")
def from_sample(sample_id: str = Form(...), case_id: Optional[str] = Form(None), recovery_target_weeks: Optional[float] = Form(None)) -> Any:
    pkg = (SAMPLES / sample_id).resolve()
    if not _inside(pkg, SAMPLES) or not (pkg / "manifest.json").exists():
        raise HTTPException(404, "unknown sample package")
    inp = CaseInput(package_dir=str(pkg), case_id=case_id, recovery_target_weeks=recovery_target_weeks)
    try:
        return core.decide_and_ask(inp).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/cases/{case_id}/apply-sample-revision")
def apply_sample_revision(case_id: str, sample_id: str = Form(...), label: str = Form(...)) -> Any:
    pkg = (SAMPLES / sample_id).resolve()
    if not _inside(pkg, SAMPLES) or not (pkg / "manifest.json").exists():
        raise HTTPException(404, "unknown sample package")
    manifest, _ = core.load_manifest(str(pkg))
    rev = next((r for r in manifest.get("revisions", []) if r["label"] == label), None)
    if rev is None:
        raise HTTPException(404, "unknown revision")
    docs = [DocumentInput(**d) for d in rev["documents"]]
    try:
        return core.decide_and_ask(CaseInput(case_id=case_id, package_dir=str(pkg), revised_documents=docs)).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/upload")
async def upload(
    files: list[UploadFile] = File(...),
    roles: str = Form(...),
    revisions: Optional[str] = Form(None),
    case_id: Optional[str] = Form(None),
    recovery_target_weeks: Optional[float] = Form(None),
    project_facts_json: Optional[str] = Form(None),
) -> Any:
    role_list = [r.strip() for r in roles.split(",")]
    rev_list = [r.strip() or None for r in revisions.split(",")] if revisions else [None] * len(files)
    if len(role_list) != len(files):
        raise HTTPException(400, "give one role per file (comma separated, in file order)")
    docs: list[DocumentInput] = []
    for f, role, rev in zip(files, role_list, rev_list + [None] * len(files)):
        if role not in {"spec", "original", "alternate", "logistics", "schedule"}:
            raise HTTPException(400, f"unknown role '{role}'")
        data = await f.read()
        docs.append(DocumentInput(role=role, content_base64=base64.b64encode(data).decode("ascii"), name=f.filename, revision=rev))  # type: ignore[arg-type]
    facts = json.loads(project_facts_json) if project_facts_json else None
    inp = CaseInput(case_id=case_id, documents=docs, project_facts=facts, recovery_target_weeks=recovery_target_weeks)
    try:
        return core.decide_and_ask(inp).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.post("/api/cases/{case_id}/revise")
async def revise(case_id: str, file: UploadFile = File(...), role: str = Form("alternate"), revision: Optional[str] = Form(None)) -> Any:
    if role not in {"spec", "original", "alternate", "logistics", "schedule"}:
        raise HTTPException(400, f"unknown role '{role}'")
    data = await file.read()
    doc = DocumentInput(role=role, content_base64=base64.b64encode(data).decode("ascii"), name=file.filename, revision=revision)  # type: ignore[arg-type]
    try:
        return core.decide_and_ask(CaseInput(case_id=case_id, revised_documents=[doc])).model_dump(mode="json")
    except (ValueError, FileNotFoundError) as exc:
        raise _err(exc)


@app.get("/api/cases")
def list_cases() -> Any:
    return core.get_store().list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> Any:
    st = core.get_store()
    latest = st.latest_decision(case_id)
    if latest is None:
        raise HTTPException(404, "no decision for this case yet")
    latest["history"] = st.history(case_id)
    return {"decision": latest, "history": st.history(case_id), "document_revisions": st.document_revisions(case_id)}


class ClarificationUpdate(BaseModel):
    question: str
    party: str
    sent: bool


@app.get("/api/cases/{case_id}/clarifications")
def get_clarifications(case_id: str) -> Any:
    """The clarification queue of the latest decision, with the saved sent/not-sent state of each question."""
    st = core.get_store()
    latest = st.latest_decision(case_id)
    if latest is None:
        raise HTTPException(404, "no decision for this case yet")
    state = st.clarification_state(case_id)
    out = []
    for party, key in (("Vendor", "vendor_questions"), ("Engineer of record", "engineer_questions"), ("Readable copy", "readable_copy_requests")):
        for q in latest.get(key, []):
            k = st.question_key(q)
            out.append({"qkey": k, "party": party, "question": q, "sent": state.get(k, False)})
    return out


@app.post("/api/cases/{case_id}/clarifications")
def update_clarification(case_id: str, body: ClarificationUpdate) -> Any:
    st = core.get_store()
    if not st.case_exists(case_id):
        raise HTTPException(404, "unknown case")
    return st.set_clarification(case_id, body.question, body.party, body.sent)


@app.get("/api/cases/{case_id}/versions/{version}")
def get_version(case_id: str, version: int) -> Any:
    d = core.get_store().get_decision(case_id, version)
    if d is None:
        raise HTTPException(404, "unknown version")
    return d


@app.get("/api/cases/{case_id}/compare")
def case_compare(case_id: str) -> Any:
    try:
        return core.compare_substitution(CaseInput(case_id=case_id)).model_dump(mode="json")
    except ValueError as exc:
        raise _err(exc)


@app.get("/api/cases/{case_id}/screen")
def case_screen(case_id: str) -> Any:
    try:
        return core.screen_consequences(CaseInput(case_id=case_id)).model_dump(mode="json")
    except ValueError as exc:
        raise _err(exc)


@app.get("/api/cases/{case_id}/page")
def case_page(case_id: str, sha: str, page: int) -> Any:
    p = core.get_store().get_page(case_id, sha, page)
    if p is None:
        raise HTTPException(404, "page not found")
    return p


if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Any:
        f = (UI_DIST / path).resolve()
        if path and _inside(f, UI_DIST) and f.is_file():
            return FileResponse(f)
        return FileResponse(UI_DIST / "index.html")
else:

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return JSONResponse({"service": "knockon", "ui": "not built (run: make ui)", "docs": "/docs"})


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="knockon-api")
    ap.add_argument("--host", default=os.environ.get("KNOCKON_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("KNOCKON_PORT", "8000")))
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
