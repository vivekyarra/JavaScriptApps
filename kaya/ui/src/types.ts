export interface Evidence {
  document: string;
  role: string;
  revision?: string | null;
  sha256: string;
  page: number;
  quote: string;
  verified: boolean;
}
export interface FollowUp {
  kind: "vendor" | "engineer" | "readable_copy" | "route" | "none";
  question?: string | null;
}
export type Label = "conclusive" | "cleared" | "needs_engineer" | "not_stated" | "could_not_read";
export interface Finding {
  key: string;
  topic: string;
  label: Label;
  title: string;
  summary: string;
  constraint?: { name: string; value: unknown; unit?: string } | null;
  requirement_evidence: Evidence[];
  supplier_evidence: Evidence[];
  formula?: string | null;
  computed: Record<string, unknown>;
  scope_note?: string | null;
  follow_up: FollowUp;
  confidence: number;
}
export interface Milestone {
  name: string;
  baseline_week?: number | null;
  alternate_week_best?: number | null;
  alternate_week_conservative?: number | null;
  max_recoverable_weeks?: number | null;
  conservative_recoverable_weeks?: number | null;
  weeks_earlier_alternate_ships?: number | null;
  controlling_item_baseline?: string | null;
  controlling_item_alternate?: string | null;
}
export interface Requirement {
  item: string;
  currently_week?: number | null;
  must_be_ready_by_week: number;
  owner?: string | null;
}
export interface Diff {
  from_version: number;
  to_version: number;
  changed: { key: string; title: string; from: string; to: string }[];
  updated: { key: string; title: string; label: string; note: string }[];
  still_open: string[];
  unchanged_settled: string[];
  new: string[];
  removed: string[];
  milestone_moved: boolean;
  answer_before?: string | null;
  answer_after?: string | null;
  max_recoverable_before?: number | null;
  max_recoverable_after?: number | null;
}
export interface DocRef {
  role: string;
  name: string;
  revision?: string | null;
  sha256: string;
  pages: number;
  unreadable_pages: number[];
}
export interface Decision {
  case_id: string;
  version: number;
  target_weeks?: number | null;
  answer: "yes" | "only_if" | "no_not_alone" | "no" | "needs_data" | "no_target";
  headline: string;
  milestone?: Milestone | null;
  conditions: string[];
  requirements_to_hit_target: Requirement[];
  next_call?: { party: string; why: string } | null;
  settled: string[];
  open: string[];
  costs: { item: string; amount: number; currency: string; source: string }[];
  cost_note: string;
  findings: Finding[];
  vendor_questions: string[];
  engineer_questions: string[];
  readable_copy_requests: string[];
  missing_project_facts: string[];
  confidence: number;
  documents: DocRef[];
  diff?: Diff | null;
  history: { version: number; created: string; answer: string; max_recoverable?: number | null }[];
  notice: string;
}
export interface FieldValue {
  field: string;
  status: "documented" | "not_stated" | "could_not_read" | "conflicting";
  value: unknown;
  unit?: string | null;
  evidence: Evidence[];
  confidence: number;
  notes: string[];
}
export interface FieldComparison {
  field: string;
  label: string;
  spec: FieldValue;
  original: FieldValue;
  alternate: FieldValue;
  changed_vs_original?: boolean | null;
  deviates_from_spec?: boolean | null;
}
export interface CompareResult {
  equipment_type: string;
  fields: FieldComparison[];
  differences: { field: string; label: string; kind: string; from_value: unknown; to_value: unknown; unit?: string | null }[];
  supplier_gaps: { field: string; label: string; status: string; reason: string }[];
  summary: string;
  documents: DocRef[];
}
export interface Sample {
  id: string;
  set: string;
  name: string;
  title: string;
  recovery_target_weeks?: number | null;
  documents: string[];
  revisions: string[];
}
export interface PageText {
  document: string;
  page: number;
  status: string;
  reason?: string | null;
  text: string;
}
