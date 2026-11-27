"""SQLite persistence: immutable document revisions and versioned decisions."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .ingest import ParsedDocument

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  created TEXT NOT NULL,
  title TEXT,
  facts_json TEXT,
  target REAL
);
CREATE TABLE IF NOT EXISTS documents (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL,
  role TEXT NOT NULL,
  name TEXT NOT NULL,
  revision TEXT,
  sha256 TEXT NOT NULL,
  created TEXT NOT NULL,
  doc_json TEXT NOT NULL,
  raw_b64 TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id, role, seq);
CREATE TABLE IF NOT EXISTS clarifications (
  case_id TEXT NOT NULL,
  qkey TEXT NOT NULL,
  question TEXT NOT NULL,
  party TEXT NOT NULL,
  sent INTEGER NOT NULL DEFAULT 0,
  updated TEXT NOT NULL,
  PRIMARY KEY (case_id, qkey)
);
CREATE TABLE IF NOT EXISTS decisions (
  case_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  created TEXT NOT NULL,
  inputs_hash TEXT NOT NULL,
  answer TEXT NOT NULL,
  max_recoverable REAL,
  output_json TEXT NOT NULL,
  PRIMARY KEY (case_id, version)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.environ.get("PHAROS_DB") or str(Path("data") / "pharos.db")
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._mem: Optional[sqlite3.Connection] = None
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self.path == ":memory:":
                if self._mem is None:
                    self._mem = sqlite3.connect(":memory:", check_same_thread=False)
                    self._mem.row_factory = sqlite3.Row
                conn = self._mem
                yield conn
                conn.commit()
                return
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------ cases
    def ensure_case(self, case_id: str, title: Optional[str] = None) -> None:
        with self._conn() as c:
            if c.execute("SELECT 1 FROM cases WHERE id=?", (case_id,)).fetchone() is None:
                c.execute("INSERT INTO cases(id, created, title) VALUES (?,?,?)", (case_id, _now(), title))

    def case_exists(self, case_id: str) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM cases WHERE id=?", (case_id,)).fetchone() is not None

    def set_case_inputs(self, case_id: str, facts: Optional[dict[str, Any]], target: Optional[float]) -> None:
        with self._conn() as c:
            row = c.execute("SELECT facts_json, target FROM cases WHERE id=?", (case_id,)).fetchone()
            cur_facts = json.loads(row["facts_json"]) if row and row["facts_json"] else {}
            if facts:
                cur_facts.update(facts)
            cur_target = target if target is not None else (row["target"] if row else None)
            c.execute(
                "UPDATE cases SET facts_json=?, target=? WHERE id=?",
                (json.dumps(cur_facts, sort_keys=True), cur_target, case_id),
            )

    def case_inputs(self, case_id: str) -> tuple[dict[str, Any], Optional[float]]:
        with self._conn() as c:
            row = c.execute("SELECT facts_json, target FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return {}, None
        return (json.loads(row["facts_json"]) if row["facts_json"] else {}), row["target"]

    def list_cases(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT c.id, c.created, c.title, c.target, "
                "(SELECT MAX(version) FROM decisions d WHERE d.case_id=c.id) AS version, "
                "(SELECT answer FROM decisions d WHERE d.case_id=c.id ORDER BY version DESC LIMIT 1) AS answer "
                "FROM cases c ORDER BY c.created DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- documents
    def active_documents(self, case_id: str) -> dict[str, ParsedDocument]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT d.role, d.doc_json FROM documents d JOIN "
                "(SELECT role, MAX(seq) AS m FROM documents WHERE case_id=? GROUP BY role) x "
                "ON d.role=x.role AND d.seq=x.m WHERE d.case_id=?",
                (case_id, case_id),
            ).fetchall()
        return {r["role"]: ParsedDocument.model_validate_json(r["doc_json"]) for r in rows}

    @staticmethod
    def storage_role(doc: ParsedDocument) -> str:
        return f"library:{doc.name}" if doc.role == "library" else doc.role

    def add_document(self, case_id: str, doc: ParsedDocument) -> bool:
        """Insert a new immutable revision unless it is identical to the active one. True if new."""
        active = self.active_documents(case_id).get(self.storage_role(doc))
        if active is not None and active.sha256 == doc.sha256 and active.revision == doc.revision:
            return False
        with self._conn() as c:
            c.execute(
                "INSERT INTO documents(case_id, role, name, revision, sha256, created, doc_json, raw_b64) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (case_id, self.storage_role(doc), doc.name, doc.effective_revision, doc.sha256, _now(), doc.model_dump_json(), doc.raw_b64),
            )
        return True

    def document_revisions(self, case_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT seq, role, name, revision, sha256, created FROM documents WHERE case_id=? ORDER BY seq", (case_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_page(self, case_id: str, sha256: str, page: int) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT doc_json FROM documents WHERE case_id=? AND sha256=? ORDER BY seq DESC LIMIT 1", (case_id, sha256)
            ).fetchone()
        if not row:
            return None
        doc = ParsedDocument.model_validate_json(row["doc_json"])
        for p in doc.pages:
            if p.number == page:
                return {"document": doc.name, "role": doc.role, "page": p.number, "status": p.status, "reason": p.reason, "text": p.text}
        return None

    # ---------------------------------------------------------- clarifications
    @staticmethod
    def question_key(question: str) -> str:
        import hashlib

        return hashlib.sha1(question.strip().encode("utf-8")).hexdigest()[:16]  # noqa: S324 - not security relevant

    def set_clarification(self, case_id: str, question: str, party: str, sent: bool) -> dict[str, Any]:
        key = self.question_key(question)
        with self._conn() as c:
            c.execute(
                "INSERT INTO clarifications(case_id, qkey, question, party, sent, updated) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(case_id, qkey) DO UPDATE SET sent=excluded.sent, updated=excluded.updated",
                (case_id, key, question, party, 1 if sent else 0, _now()),
            )
        return {"qkey": key, "question": question, "party": party, "sent": sent}

    def clarification_state(self, case_id: str) -> dict[str, bool]:
        with self._conn() as c:
            rows = c.execute("SELECT qkey, sent FROM clarifications WHERE case_id=?", (case_id,)).fetchall()
        return {r["qkey"]: bool(r["sent"]) for r in rows}

    # -------------------------------------------------------------- decisions
    def latest_decision(self, case_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT output_json FROM decisions WHERE case_id=? ORDER BY version DESC LIMIT 1", (case_id,)
            ).fetchone()
        return json.loads(row["output_json"]) if row else None

    def get_decision(self, case_id: str, version: int) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT output_json FROM decisions WHERE case_id=? AND version=?", (case_id, version)
            ).fetchone()
        return json.loads(row["output_json"]) if row else None

    def latest_hash(self, case_id: str) -> Optional[str]:
        with self._conn() as c:
            row = c.execute(
                "SELECT inputs_hash FROM decisions WHERE case_id=? ORDER BY version DESC LIMIT 1", (case_id,)
            ).fetchone()
        return row["inputs_hash"] if row else None

    def next_version(self, case_id: str) -> int:
        with self._conn() as c:
            row = c.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM decisions WHERE case_id=?", (case_id,)).fetchone()
        return int(row["v"])

    def save_decision(self, case_id: str, version: int, inputs_hash: str, answer: str, max_rec: Optional[float], output: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO decisions(case_id, version, created, inputs_hash, answer, max_recoverable, output_json) VALUES (?,?,?,?,?,?,?)",
                (case_id, version, _now(), inputs_hash, answer, max_rec, json.dumps(output)),
            )

    def history(self, case_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT version, created, answer, max_recoverable, inputs_hash FROM decisions WHERE case_id=? ORDER BY version",
                (case_id,),
            ).fetchall()
        return [dict(r) for r in rows]
