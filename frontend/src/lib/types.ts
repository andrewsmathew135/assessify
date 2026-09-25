// Types mirroring the backend Pydantic schemas.

export type FileType = "docx" | "xlsx";
export type SessionStatus = "pending" | "opened" | "submitted" | "expired";
export type ReviewStatus = "pending" | "passed" | "failed" | "needs_review";
export type SubmissionSource = "upload" | "in_browser";
export type FieldValueType = "string" | "number" | "integer" | "boolean" | "date";

export interface FieldDefinition {
  id: string;
  label: string;
  type: FieldValueType;
  required: boolean;
  help_text?: string | null;
  sheet?: string | null;
  cell?: string | null;
  placeholder?: string | null;
  rich_text: boolean;
  min?: number | null;
  max?: number | null;
  min_length?: number | null;
  max_length?: number | null;
  pattern?: string | null;
  allowed_values?: string[] | null;
}

export interface FieldSpec {
  fields: FieldDefinition[];
}

export interface TemplateListItem {
  id: string;
  name: string;
  file_type: FileType;
  original_filename: string;
  created_at: string;
}

export interface Template {
  id: string;
  name: string;
  instructions: string;
  file_type: FileType;
  original_filename: string;
  field_spec: FieldSpec;
  created_at: string;
}

export interface SessionLink {
  id: string;
  template_id: string;
  token: string;
  candidate_name?: string | null;
  candidate_email?: string | null;
  status: SessionStatus;
  created_at: string;
  opened_at?: string | null;
  expires_at?: string | null;
  candidate_url: string;
}

export interface CandidateAssignment {
  session_token: string;
  status: SessionStatus;
  candidate_name?: string | null;
  template_name: string;
  instructions: string;
  file_type: FileType;
  field_spec: FieldSpec;
  expires_at?: string | null;
  already_submitted: boolean;
}

export interface Cell {
  address: string;
  value: unknown;
  formula?: string | null;
  editable: boolean;
}

export interface Sheet {
  name: string;
  rows: Cell[][];
  n_rows: number;
  n_cols: number;
}

export interface WorkbookView {
  file_type: "xlsx";
  sheets: Sheet[];
  fields: FieldDefinition[];
}

export type DocRun = { text: string } | { field: string };

export interface DocBlock {
  type: string;
  style?: string | null;
  runs: DocRun[];
}

export interface DocumentView {
  file_type: "docx";
  blocks: DocBlock[];
  fields: FieldDefinition[];
}

export interface DocumentHtml {
  file_type: "docx";
  html: string;
  fields: FieldDefinition[];
}

export interface SubmitEditsBody {
  field_values?: Record<string, unknown>;
  cell_edits?: Record<string, Record<string, unknown>>;
  document_html?: string;
}

export interface CheckResult {
  id: string;
  label: string;
  passed: boolean;
  severity: "error" | "warning" | "info";
  message: string;
}

export interface ReviewReport {
  status: ReviewStatus;
  summary: string;
  checks: CheckResult[];
  passed_count: number;
  failed_count: number;
  warning_count: number;
}

export interface FieldDiff {
  field_id: string;
  label: string;
  original: unknown;
  submitted: unknown;
  changed: boolean;
}

export interface DiffSummary {
  fields: FieldDiff[];
  changed_count: number;
}

export interface SubmissionConfirmation {
  submission_id: string;
  submitted_filename: string;
  review_status: ReviewStatus;
  summary: string;
  fields_submitted: Record<string, unknown>;
}

export interface DashboardRow {
  submission_id: string;
  session_id: string;
  template_id: string;
  template_name: string;
  candidate_name?: string | null;
  candidate_email?: string | null;
  submitted_filename: string;
  source: SubmissionSource;
  review_status: ReviewStatus;
  score?: number | null;
  created_at: string;
}

export interface SubmissionDetail {
  id: string;
  session_id: string;
  template_id: string;
  submitted_filename: string;
  source: SubmissionSource;
  field_values: Record<string, unknown>;
  review_status: ReviewStatus;
  review_report?: ReviewReport | null;
  diff_summary?: DiffSummary | null;
  score?: number | null;
  created_at: string;
  reviewed_at?: string | null;
  candidate_name?: string | null;
  candidate_email?: string | null;
  template_name: string;
  file_type: FileType;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}
