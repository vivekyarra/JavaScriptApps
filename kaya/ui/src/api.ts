import type { CompareResult, Decision, PageText, Sample } from "./types";

async function check(r: Response) {
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const body = await r.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(msg);
  }
  return r.json();
}

export const api = {
  samples: (): Promise<Sample[]> => fetch("/api/samples").then(check),
  fromSample: (sampleId: string, caseId: string): Promise<Decision> => {
    const f = new FormData();
    f.set("sample_id", sampleId);
    f.set("case_id", caseId);
    return fetch("/api/cases/from-sample", { method: "POST", body: f }).then(check);
  },
  applySampleRevision: (caseId: string, sampleId: string, label: string): Promise<Decision> => {
    const f = new FormData();
    f.set("sample_id", sampleId);
    f.set("label", label);
    return fetch(`/api/cases/${caseId}/apply-sample-revision`, { method: "POST", body: f }).then(check);
  },
  upload: (files: { file: File; role: string; revision: string }[], target: string, facts: string): Promise<Decision> => {
    const f = new FormData();
    files.forEach((x) => f.append("files", x.file));
    f.set("roles", files.map((x) => x.role).join(","));
    f.set("revisions", files.map((x) => x.revision).join(","));
    if (target) f.set("recovery_target_weeks", target);
    if (facts.trim()) f.set("project_facts_json", facts);
    return fetch("/api/upload", { method: "POST", body: f }).then(check);
  },
  revise: (caseId: string, file: File, role: string, revision: string): Promise<Decision> => {
    const f = new FormData();
    f.set("file", file);
    f.set("role", role);
    if (revision) f.set("revision", revision);
    return fetch(`/api/cases/${caseId}/revise`, { method: "POST", body: f }).then(check);
  },
  setTarget: (caseId: string, target: number): Promise<Decision> =>
    fetch("/api/tools/decide", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ case_id: caseId, recovery_target_weeks: target }),
    }).then(check),
  compare: (caseId: string): Promise<CompareResult> => fetch(`/api/cases/${caseId}/compare`).then(check),
  page: (caseId: string, sha: string, page: number): Promise<PageText> =>
    fetch(`/api/cases/${caseId}/page?sha=${sha}&page=${page}`).then(check),
  clarifications: (caseId: string): Promise<{ qkey: string; party: string; question: string; sent: boolean }[]> =>
    fetch(`/api/cases/${caseId}/clarifications`).then(check),
  setClarification: (caseId: string, question: string, party: string, sent: boolean) =>
    fetch(`/api/cases/${caseId}/clarifications`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, party, sent }),
    }).then(check),
  version: (caseId: string, v: number): Promise<Decision> => fetch(`/api/cases/${caseId}/versions/${v}`).then(check),
};
