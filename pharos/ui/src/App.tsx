import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { SubmittalCheck, CompareResult, Decision, Evidence, FieldValue, Finding, Label, PageText, Sample } from "./types";

const LABELS: Record<Label, { text: string; icon: string; hint: string }> = {
  conclusive: { text: "Conclusive", icon: "●", hint: "A documented value breaks a documented project constraint" },
  cleared: { text: "Cleared", icon: "✓", hint: "Meets that one constraint only" },
  needs_engineer: { text: "Needs engineer", icon: "!", hint: "The change alters a study input; only a study settles it" },
  not_stated: { text: "Not stated", icon: "?", hint: "The readable submittal does not give the value" },
  could_not_read: { text: "Could not read", icon: "…", hint: "The relevant text could not be read reliably" },
};
const ANSWERS: Record<Decision["answer"], string> = {
  yes: "Yes",
  only_if: "Only if…",
  no_not_alone: "No, not from this swap alone",
  no: "No",
  needs_data: "Needs data",
  no_target: "No target set",
};
const KEY_NAMES: Record<string, string> = {
  "weight:elevator": "Heaviest shipping section vs freight elevator",
  "weight:slab": "Floor loading",
  "dims:door": "Overall dimensions vs door",
  "dims:ceiling": "Height vs overhead clearance",
  "heat:cooling": "Heat loss vs cooling allowance",
  "electrical:impedance": "Impedance (%Z)",
  "electrical:reactance": "Subtransient reactance",
  "spec:kva": "Rated kVA vs specification",
  "spec:primary_voltage": "Primary voltage vs specification",
  "spec:secondary_voltage": "Secondary voltage vs specification",
  "spec:winding": "Winding configuration",
};
const STATUS_TEXT: Record<FieldValue["status"], string> = {
  documented: "documented",
  not_stated: "not stated",
  could_not_read: "could not read",
  conflicting: "conflicting",
};

function Chip({ label }: { label: Label }) {
  const l = LABELS[label];
  return (
    <span className={`chip chip-${label}`} title={l.hint}>
      <span aria-hidden="true">{l.icon}</span> {l.text}
    </span>
  );
}

function fmtValue(v: unknown, unit?: string | null): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return `${Number.isInteger(v) ? v.toLocaleString() : Number(v.toFixed(2)).toLocaleString()}${unit ? " " + unit : ""}`;
  if (Array.isArray(v)) return v.join(" × ") + (unit ? " " + unit : "");
  if (typeof v === "object") {
    const o = v as Record<string, number>;
    if ("unordered" in o) return (o.unordered as unknown as number[]).map((n) => Math.round(n)).join(" × ") + " mm (order not labelled)";
    return Object.entries(o).map(([k, n]) => `${k[0].toUpperCase()} ${Math.round(Number(n))}`).join("  ") + " mm";
  }
  return String(v);
}

function EvidenceLine({ ev, caseId, onOpen }: { ev: Evidence; caseId: string; onOpen: (e: Evidence) => void }) {
  const isFact = ev.role === "facts";
  return (
    <div className="evidence">
      <div className="evidence-meta">
        {ev.document}
        {ev.revision ? `, rev ${ev.revision}` : ""}
        {isFact ? " (supplied project fact)" : `, p.${ev.page}`}
        {!ev.verified && <span className="warn"> · quote not verified</span>}
      </div>
      <blockquote>{ev.quote}</blockquote>
      {!isFact && (
        <button className="link" onClick={() => onOpen(ev)} aria-label={`Open page ${ev.page} of ${ev.document}`}>
          open page {ev.page}
        </button>
      )}
      <span hidden>{caseId}</span>
    </div>
  );
}

function PageViewer({ caseId, ev, onClose }: { caseId: string; ev: Evidence; onClose: () => void }) {
  const [page, setPage] = useState<PageText | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.page(caseId, ev.sha256, ev.page).then(setPage).catch((e) => setErr(String(e.message)));
  }, [caseId, ev]);
  const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLowerCase();
  const q = norm(ev.quote);
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Source page">
      <div className="modal-card">
        <div className="modal-head">
          <strong>{ev.document}</strong> · page {ev.page}
          <button onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>
        {err && <p className="warn">{err}</p>}
        {page && (
          <pre className="page-text">
            {page.text.split("\n").map((line, i) => {
              const n = norm(line);
              const hit = n.length > 3 && (q.includes(n) || n.includes(q));
              return (
                <div key={i} className={hit ? "hit" : undefined}>
                  {line || " "}
                </div>
              );
            })}
          </pre>
        )}
      </div>
    </div>
  );
}

function FindingCard({ f, caseId, onOpen }: { f: Finding; caseId: string; onOpen: (e: Evidence) => void }) {
  const [open, setOpen] = useState(f.label === "conclusive");
  return (
    <article className={`card finding finding-${f.label}`}>
      <header onClick={() => setOpen(!open)} className="finding-head" role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(!open)}>
        <Chip label={f.label} />
        <span className="finding-title">{f.title}</span>
        <span className="muted">{f.topic}</span>
        <span className="muted">{open ? "▾" : "▸"}</span>
      </header>
      <p className="summary">{f.summary}</p>
      {open && (
        <div className="finding-body">
          <div className="side-by-side">
            <section>
              <h4>Requirement</h4>
              {f.constraint && (
                <p className="constraint">
                  {f.constraint.name.replace(/\s*\([^)]*\)\s*$/, "")}: <strong>{fmtValue(f.constraint.value, f.constraint.unit)}</strong>
                </p>
              )}
              {f.requirement_evidence.length === 0 && <p className="muted">No requirement cited for this finding.</p>}
              {f.requirement_evidence.map((e, i) => (
                <EvidenceLine key={i} ev={e} caseId={caseId} onOpen={onOpen} />
              ))}
            </section>
            <section>
              <h4>Supplier support</h4>
              {f.supplier_evidence.length === 0 && <p className="muted">The supplier documents give nothing to cite.</p>}
              {f.supplier_evidence.map((e, i) => (
                <EvidenceLine key={i} ev={e} caseId={caseId} onOpen={onOpen} />
              ))}
            </section>
          </div>
          {f.formula && (
            <p className="formula">
              <code>{f.formula}</code>
            </p>
          )}
          {f.scope_note && <p className="scope">{f.scope_note}</p>}
          {f.follow_up.question && (
            <p className="followup">
              <strong>
                {f.follow_up.kind === "engineer" ? "Ask the engineer of record" : f.follow_up.kind === "readable_copy" ? "Request a readable copy" : "Ask the vendor"}:
              </strong>{" "}
              {f.follow_up.question}
            </p>
          )}
          <p className="muted">Confidence {f.confidence ? f.confidence.toFixed(2) : "n/a"} · key {f.key}</p>
        </div>
      )}
    </article>
  );
}

function Overview({ d, onTarget }: { d: Decision; onTarget: (n: number) => void }) {
  const m = d.milestone;
  const [t, setT] = useState(d.target_weeks != null ? String(d.target_weeks) : "");
  useEffect(() => setT(d.target_weeks != null ? String(d.target_weeks) : ""), [d.target_weeks, d.version]);
  return (
    <section aria-label="Decision">
      <div className={`card answer answer-${d.answer}`}>
        <div className="answer-top">
          <span className="answer-badge">{ANSWERS[d.answer]}</span>
          <label className="target">
            Weeks we need to recover
            <input type="number" min={0} value={t} onChange={(e) => setT(e.target.value)} />
            <button onClick={() => t !== "" && onTarget(Number(t))}>Ask</button>
          </label>
        </div>
        <p className="headline">{d.headline}</p>
        {d.next_call && (
          <p className="nextcall">
            <strong>Call next:</strong> {d.next_call.party}. <span className="muted">{d.next_call.why}</span>
          </p>
        )}
      </div>
      {m && (
        <div className="grid4">
          <div className="stat"><span className="stat-n">{m.baseline_week ?? "—"}</span><span>baseline week for {m.name.toLowerCase()}</span></div>
          <div className="stat"><span className="stat-n">{m.weeks_earlier_alternate_ships ?? "—"}</span><span>weeks earlier the alternate ships</span></div>
          <div className="stat"><span className="stat-n">{m.max_recoverable_weeks ?? "—"}</span><span>most weeks the project can recover</span></div>
          <div className="stat"><span className="stat-n">{m.controlling_item_alternate ?? "—"}</span><span>controls the milestone with the alternate</span></div>
        </div>
      )}
      {d.requirements_to_hit_target.length > 0 && (
        <div className="card">
          <h3>To hit the target</h3>
          <ul>
            {d.requirements_to_hit_target.map((r, i) => (
              <li key={i}>
                <strong>{r.item}</strong> must be ready by week <strong>{r.must_be_ready_by_week}</strong> (now week {r.currently_week ?? "?"}
                {r.owner ? `, owner: ${r.owner}` : ""})
              </li>
            ))}
          </ul>
        </div>
      )}
      {d.options && d.options.length > 0 && (
        <div className="card">
          <h3>Recovery options at the same milestone</h3>
          {d.recommendation && <p><strong>{d.recommendation}</strong></p>}
          <div className="tablewrap"><table>
            <thead><tr><th>Option</th><th>Ready week</th><th>Weeks recovered (best / conservative)</th><th>Target</th><th>Cost</th></tr></thead>
            <tbody>{d.options.map((o) => (
              <tr key={o.id}>
                <td>{o.description}{o.owner ? <span className="muted"> · {o.owner}</span> : null}
                  {o.conditions.length > 0 && <ul>{o.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>}
                  {o.next_action && <p className="muted">{o.next_action}</p>}</td>
                <td>{o.ready_week ?? "—"}</td>
                <td>{o.recovery_weeks_best ?? "—"} / {o.recovery_weeks_conservative ?? "—"}</td>
                <td>{(o.target_status ?? "").replace(/_/g, " ")}</td>
                <td>{o.incremental_cost != null ? o.incremental_cost.toLocaleString() : <span className="muted">not documented</span>}</td>
              </tr>))}</tbody>
          </table></div>
        </div>
      )}
      {d.ranking && d.ranking.length > 0 && (
        <div className="card">
          <h3>PO lines by effect on the milestone</h3>
          <div className="tablewrap"><table>
            <thead><tr><th>Line</th><th>Ready week</th><th>Float</th><th>Margin to deadline</th><th>Action</th></tr></thead>
            <tbody>{d.ranking.map((r) => (
              <tr key={r.line_id}><td>{r.name}{r.owner ? <span className="muted"> · {r.owner}</span> : null}</td><td>{r.ready_week ?? "—"}</td><td>{r.float_to_handoff_weeks ?? "—"}</td><td>{r.margin_to_deadline_weeks ?? "—"}</td><td>{r.action.replace(/_/g, " ")}</td></tr>))}</tbody>
          </table></div>
        </div>
      )}
      <div className="card">
        <h3>Conditions behind this answer</h3>
        {d.conditions.length ? <ul>{d.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul> : <p className="muted">None stated.</p>}
        {d.cost_note && <p className="costnote">{d.cost_note}</p>}
        {d.costs.map((c, i) => (
          <p key={i}>
            {c.item}: {c.amount.toLocaleString()} {c.currency} <span className="muted">(source: {c.source})</span>
          </p>
        ))}
        {d.missing_project_facts.length > 0 && (
          <>
            <h4>Project facts not provided</h4>
            <ul>{d.missing_project_facts.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </>
        )}
      </div>
      <p className="notice">{d.notice}</p>
    </section>
  );
}

function CompareTable({ caseId }: { caseId: string }) {
  const [c, setC] = useState<CompareResult | null>(null);
  const [err, setErr] = useState("");
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    api.compare(caseId).then(setC).catch((e) => setErr(e.message));
  }, [caseId]);
  if (err) return <p className="warn">{err}</p>;
  if (!c) return <p className="muted">Loading comparison…</p>;
  const stated = (f: CompareResult["fields"][number]) => [f.spec, f.original, f.alternate].some((v) => v.status !== "not_stated");
  const hiddenCount = c.fields.filter((f) => !stated(f)).length;
  const rows = showAll ? c.fields : c.fields.filter(stated);
  const cell = (fv: FieldValue) => (
    <td className={`cell cell-${fv.status}`}>
      <div>{fv.status === "documented" ? fmtValue(fv.value, fv.unit) : "—"}</div>
      <div className="muted small">
        {STATUS_TEXT[fv.status]}
        {fv.status === "documented" && fv.evidence[0] ? ` · p.${fv.evidence[0].page}` : ""}
        {fv.status === "documented" && fv.confidence ? ` · ${fv.confidence.toFixed(2)}` : ""}
      </div>
    </td>
  );
  return (
    <section>
      <p className="muted">{c.summary} Equipment type detected: {c.equipment_type}.</p>
      <label className="small">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show fields that no document states ({hiddenCount})
      </label>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>Field</th><th>Specification</th><th>Original equipment</th><th>Alternate</th><th>Result</th></tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.field}>
                <th scope="row">{f.label}</th>
                {cell(f.spec)}
                {cell(f.original)}
                {cell(f.alternate)}
                <td>
                  {f.changed_vs_original && <span className="tag tag-change">changed vs original</span>}
                  {f.deviates_from_spec && <span className="tag tag-dev">deviates from spec</span>}
                  {!f.changed_vs_original && !f.deviates_from_spec && f.alternate.status === "documented" && <span className="muted small">no difference found</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Not supplied or unreadable</h3>
      {c.supplier_gaps.length === 0 ? <p className="muted">Nothing missing.</p> : <ul>{c.supplier_gaps.map((g, i) => <li key={i}><strong>{g.label}</strong>: {g.reason}</li>)}</ul>}
    </section>
  );
}

function SubmittalTab({ caseId }: { caseId: string }) {
  const [r, setR] = useState<SubmittalCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.submittal(caseId).then(setR).catch((e) => setErr(e.message)); }, [caseId]);
  if (err) return <p className="warn">{err}</p>;
  if (!r) return <p className="muted">Checking the submittal…</p>;
  const ev = (e: Evidence[]) => e.slice(0, 1).map((x, i) => <span key={i} className="muted">{x.document} p.{x.page}: “{x.quote}”</span>);
  return (
    <section>
      <p>{r.summary}</p>
      {r.table_warnings.map((w, i) => <p key={i} className="warn">{w}</p>)}
      <div className="tablewrap"><table>
        <thead><tr><th>Requirement</th><th>Spec says</th><th>Submittal says</th><th>Verdict</th></tr></thead>
        <tbody>{r.requirements.map((q) => (
          <tr key={q.field}>
            <td>{q.label}</td>
            <td>{q.requirement ?? "—"} <small className="muted">({q.basis})</small><div>{ev(q.requirement_evidence)}</div></td>
            <td>{q.submittal_value ?? "—"}<div>{ev(q.submittal_evidence)}</div>
              {q.searched && <div className="muted">searched pages {q.searched.readable_pages.join(", ") || "none"} for {q.searched.looking_for}{q.searched.unreadable_pages.length ? `; unreadable: ${q.searched.unreadable_pages.join(", ")}` : ""}</div>}</td>
            <td><strong>{q.verdict}</strong></td>
          </tr>))}</tbody>
      </table></div>
    </section>
  );
}

function Queue({ d }: { d: Decision }) {
  const [items, setItems] = useState<{ qkey: string; party: string; question: string; sent: boolean }[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.clarifications(d.case_id).then(setItems).catch((e) => setErr(e.message));
  }, [d.case_id, d.version]);
  const copy = (t: string) => navigator.clipboard?.writeText(t).catch(() => undefined);
  const toggle = (it: (typeof items)[number], sent: boolean) => {
    setItems(items.map((x) => (x.qkey === it.qkey ? { ...x, sent } : x)));
    api.setClarification(d.case_id, it.question, it.party, sent).catch((e) => setErr(e.message));
  };
  const parties = ["Vendor", "Engineer of record", "Readable copy"];
  return (
    <section>
      <p className="muted">Questions drafted from the open findings. Ticking one saves that it was sent; the state is kept with the case across versions.</p>
      {err && <p className="warn">{err}</p>}
      {parties.map((party) => {
        const qs = items.filter((i) => i.party === party);
        return (
          <div className="card" key={party}>
            <h3>{party === "Readable copy" ? "Readable copy requests" : party}</h3>
            {qs.length === 0 && <p className="muted">No open questions.</p>}
            {qs.map((it) => (
              <div className="question" key={it.qkey}>
                <label>
                  <input type="checkbox" checked={it.sent} onChange={(e) => toggle(it, e.target.checked)} /> <span className={it.sent ? "done" : undefined}>{it.question}</span>
                </label>
                <button className="link" onClick={() => copy(it.question)}>copy</button>
              </div>
            ))}
          </div>
        );
      })}
    </section>
  );
}

function History({ d, sampleId, onDecision, onError }: { d: Decision; sampleId: string | null; onDecision: (d: Decision) => void; onError: (m: string) => void }) {
  const [role, setRole] = useState("alternate");
  const [rev, setRev] = useState("");
  const [sample, setSample] = useState<Sample | null>(null);
  useEffect(() => {
    if (sampleId) api.samples().then((all) => setSample(all.find((s) => s.id === sampleId) ?? null));
  }, [sampleId]);
  const diff = d.diff;
  const title = (k: string) => d.findings.find((f) => f.key === k)?.title ?? KEY_NAMES[k] ?? k;
  const run = (p: Promise<Decision>) => p.then(onDecision).catch((e) => onError(e.message));
  return (
    <section>
      <div className="card">
        <h3>Add a revised document</h3>
        <p className="muted">The same decision updates and the history keeps both revisions.</p>
        <div className="row">
          <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Document role">
            {["alternate", "spec", "original", "logistics", "schedule"].map((r) => <option key={r}>{r}</option>)}
          </select>
          <input placeholder="revision (optional)" value={rev} onChange={(e) => setRev(e.target.value)} aria-label="Revision label" />
          <input type="file" aria-label="Revised document" onChange={(e) => e.target.files?.[0] && run(api.revise(d.case_id, e.target.files[0], role, rev))} />
        </div>
        {sample?.revisions.map((label) => (
          <button key={label} onClick={() => run(api.applySampleRevision(d.case_id, sample.id, label))}>Apply the sample's revision "{label}"</button>
        ))}
      </div>
      {diff && (
        <div className="card diff">
          <h3>What changed in version {diff.to_version} (from {diff.from_version})</h3>
          <p>
            Answer: <strong>{ANSWERS[diff.answer_before as Decision["answer"]] ?? diff.answer_before}</strong> → <strong>{ANSWERS[diff.answer_after as Decision["answer"]] ?? diff.answer_after}</strong>. Milestone {diff.milestone_moved ? "moved" : "did not move"} (most recoverable {diff.max_recoverable_before} → {diff.max_recoverable_after} weeks).
          </p>
          {diff.changed.map((c) => <p key={c.key}><strong>{c.title}</strong>: {c.from.replace("_", " ")} → {c.to.replace("_", " ")}</p>)}
          {diff.updated.map((u) => <p key={u.key}><strong>{u.title}</strong>: still {u.label.replace("_", " ")}, but its details changed</p>)}
          {diff.removed.length > 0 && <p>No longer raised: {diff.removed.map(title).join("; ")}</p>}
          {diff.new.length > 0 && <p>Newly raised: {diff.new.map(title).join("; ")}</p>}
          {diff.still_open.length > 0 && <p>Still open: {diff.still_open.map(title).join("; ")}</p>}
          {diff.unchanged_settled.length > 0 && <p className="muted">Settled and unchanged: {diff.unchanged_settled.map(title).join("; ")}</p>}
        </div>
      )}
      <div className="card">
        <h3>Decision history</h3>
        <table>
          <thead><tr><th>Version</th><th>When</th><th>Answer</th><th>Most recoverable (weeks)</th></tr></thead>
          <tbody>
            {[...d.history].reverse().map((h) => (
              <tr key={h.version}><td>v{h.version}</td><td>{h.created.replace("T", " ").replace("+00:00", " UTC")}</td><td>{ANSWERS[h.answer as Decision["answer"]] ?? h.answer}</td><td>{h.max_recoverable ?? "—"}</td></tr>
            ))}
          </tbody>
        </table>
        <h4>Documents in this case</h4>
        <ul>{d.documents.map((x, i) => <li key={i}>{x.role}: {x.name}{x.revision ? ` (rev ${x.revision})` : ""} · {x.pages} page(s){x.unreadable_pages.length ? ` · unreadable: ${x.unreadable_pages.join(", ")}` : ""}</li>)}</ul>
      </div>
    </section>
  );
}

function Start({ onDecision, onError, samples }: { onDecision: (d: Decision, sampleId: string | null) => void; onError: (m: string) => void; samples: Sample[] }) {
  const roles = ["spec", "original", "alternate", "logistics", "schedule"];
  const [files, setFiles] = useState<Record<string, File | undefined>>({});
  const [target, setTarget] = useState("");
  const [facts, setFacts] = useState("");
  const [busy, setBusy] = useState(false);
  const bySet = useMemo(() => {
    const m: Record<string, Sample[]> = {};
    samples.forEach((s) => (m[s.set] = [...(m[s.set] ?? []), s]));
    return m;
  }, [samples]);
  const go = (p: Promise<Decision>, sampleId: string | null) => {
    setBusy(true);
    p.then((d) => onDecision(d, sampleId)).catch((e) => onError(e.message)).finally(() => setBusy(false));
  };
  const submit = () => {
    const list = roles.filter((r) => files[r]).map((r) => ({ file: files[r]!, role: r, revision: "" }));
    if (!list.some((x) => x.role === "alternate")) return onError("An alternate (supplier submittal) file is required.");
    go(api.upload(list, target, facts), null);
  };
  return (
    <aside className="start">
      <h2>Start a case</h2>
      <h3>Sample packages</h3>
      <p className="muted small">Synthetic documents; fictional vendors.</p>
      {Object.entries(bySet).map(([set, list]) => (
        <div key={set}>
          <h4>{set}</h4>
          {list.map((s) => (
            <button key={s.id} className="sample" disabled={busy} onClick={() => go(api.fromSample(s.id, `ui-${s.name}`), s.id)}>
              <strong>{s.name}</strong>
              <span>{s.title}</span>
            </button>
          ))}
        </div>
      ))}
      <h3>Your own documents</h3>
      <p className="muted small">Text-based PDFs (or .txt). Scanned pages are flagged, not guessed.</p>
      {roles.map((r) => (
        <label key={r} className="filerow">
          {r === "alternate" ? "alternate (required)" : r}
          <input type="file" onChange={(e) => setFiles({ ...files, [r]: e.target.files?.[0] })} />
        </label>
      ))}
      <label className="filerow">Weeks we need to recover<input type="number" min={0} value={target} onChange={(e) => setTarget(e.target.value)} /></label>
      <label className="filerow">Project facts (JSON, optional)<textarea rows={3} value={facts} onChange={(e) => setFacts(e.target.value)} placeholder='{"elevator_capacity_kg": 3600}' /></label>
      <button className="primary" disabled={busy} onClick={submit}>{busy ? "Working…" : "Run the three tools"}</button>
    </aside>
  );
}

export default function App() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [d, setD] = useState<Decision | null>(null);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [tab, setTab] = useState<"overview" | "findings" | "submittal" | "compare" | "queue" | "history">("overview");
  const [err, setErr] = useState("");
  const [viewer, setViewer] = useState<Evidence | null>(null);
  useEffect(() => {
    api.samples().then(setSamples).catch((e) => setErr(e.message));
  }, []);
  const onDecision = useCallback((x: Decision, sid?: string | null) => {
    setD(x);
    if (sid !== undefined) setSampleId(sid);
    setErr("");
  }, []);
  const tabs: [typeof tab, string][] = [["overview", "Overview"], ["findings", "Findings"], ["submittal", "Submittal check"], ["compare", "Compare"], ["queue", "Clarification queue"], ["history", "History"]];
  const counts = d ? { questions: d.vendor_questions.length + d.engineer_questions.length + d.readable_copy_requests.length } : null;
  return (
    <div className="app">
      <header className="top">
        <h1>Pharos</h1>
        <span className="muted">What does this substitute change, and how many weeks can the project really recover?</span>
      </header>
      {err && <div className="error" role="alert">{err}</div>}
      <div className="layout">
        <Start samples={samples} onDecision={(x, sid) => { onDecision(x, sid); setTab("overview"); }} onError={setErr} />
        <main>
          {!d && <div className="card empty"><h2>Pick a sample package or upload your documents</h2><p>Pharos compares the alternate with the specification and the original equipment, links each change to your project's constraints, and tells you how many weeks it can recover. It pre-screens only; it never approves engineering.</p></div>}
          {d && (
            <>
              <div className="caseline"><strong>{d.case_id}</strong> · version {d.version} · confidence {d.confidence.toFixed(2)}</div>
              <nav className="tabs" role="tablist">
                {tabs.map(([k, label]) => (
                  <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "active" : undefined} onClick={() => setTab(k)}>
                    {label}{k === "findings" ? ` (${d.findings.length})` : k === "queue" && counts ? ` (${counts.questions})` : ""}
                  </button>
                ))}
              </nav>
              {tab === "overview" && <Overview d={d} onTarget={(n) => api.setTarget(d.case_id, n).then((x) => onDecision(x)).catch((e) => setErr(e.message))} />}
              {tab === "findings" && (
                <section>
                  <p className="muted">Settled: {d.settled.length} · Open: {d.open.length}. Open a finding to see the requirement beside the supplier's support.</p>
                  {d.findings.length === 0 && <p>No findings. Provide site limits (project facts or a logistics document) to screen physical constraints.</p>}
                  {d.findings.map((f) => <FindingCard key={f.key} f={f} caseId={d.case_id} onOpen={setViewer} />)}
                </section>
              )}
              {tab === "submittal" && <SubmittalTab caseId={d.case_id} key={`${d.case_id}-${d.version}`} />}
              {tab === "compare" && <CompareTable caseId={d.case_id} key={`${d.case_id}-${d.version}`} />}
              {tab === "queue" && <Queue d={d} />}
              {tab === "history" && <History d={d} sampleId={sampleId} onDecision={(x) => onDecision(x)} onError={setErr} />}
            </>
          )}
        </main>
      </div>
      {viewer && d && <PageViewer caseId={d.case_id} ev={viewer} onClose={() => setViewer(null)} />}
    </div>
  );
}
