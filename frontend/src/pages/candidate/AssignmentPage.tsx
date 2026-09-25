import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { FileDropzone } from "../../components/FileDropzone";
import { RichTextEditor } from "../../components/RichTextEditor";
import { SpreadsheetEditor, type GridChange } from "../../components/SpreadsheetEditor";
import { useToast } from "../../components/Toast";
import { Alert, LoadingScreen, ReviewBadge, Spinner } from "../../components/ui";
import { candidateApi, RequestError } from "../../lib/api";
import { useAsync } from "../../lib/hooks";
import type { CandidateAssignment, SubmissionConfirmation } from "../../lib/types";

export function AssignmentPage() {
  const { token = "" } = useParams();
  const { data, loading, error } = useAsync(() => candidateApi.openAssignment(token), [token]);
  const [confirmation, setConfirmation] = useState<SubmissionConfirmation | null>(null);

  if (loading) return <PublicShell><LoadingScreen label="Opening your assignment…" /></PublicShell>;
  if (error)
    return (
      <PublicShell>
        <Alert kind="error">{error}</Alert>
      </PublicShell>
    );
  if (!data) return null;

  if (confirmation) {
    return (
      <PublicShell>
        <ConfirmationView confirmation={confirmation} />
      </PublicShell>
    );
  }

  if (data.status === "expired") {
    return (
      <PublicShell>
        <Alert kind="warning">
          This assignment link has expired. Please contact the person who sent it to you.
        </Alert>
      </PublicShell>
    );
  }

  return (
    <PublicShell>
      <AssignmentBody assignment={data} token={token} onSubmitted={setConfirmation} />
    </PublicShell>
  );
}

function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-2 px-4 py-4 font-extrabold tracking-tight text-slate-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            A
          </span>
          Assessify
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
    </div>
  );
}

function AssignmentBody({
  assignment,
  token,
  onSubmitted,
}: {
  assignment: CandidateAssignment;
  token: string;
  onSubmitted: (c: SubmissionConfirmation) => void;
}) {
  const [tab, setTab] = useState<"edit" | "upload">("edit");

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-slate-900">{assignment.template_name}</h1>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {assignment.file_type}
          </span>
        </div>
        {assignment.candidate_name && (
          <p className="mt-1 text-sm text-slate-500">For: {assignment.candidate_name}</p>
        )}
        {assignment.instructions && (
          <div className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
            {assignment.instructions}
          </div>
        )}
        {assignment.already_submitted && (
          <div className="mt-4">
            <Alert kind="info">
              You’ve already submitted this assignment. Submitting again will add a new submission.
            </Alert>
          </div>
        )}
      </div>

      <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
        <TabButton active={tab === "edit"} onClick={() => setTab("edit")}>
          Edit in browser
        </TabButton>
        <TabButton active={tab === "upload"} onClick={() => setTab("upload")}>
          Upload a file
        </TabButton>
      </div>

      {tab === "edit" ? (
        <InBrowserEditor assignment={assignment} token={token} onSubmitted={onSubmitted} />
      ) : (
        <UploadPanel assignment={assignment} token={token} onSubmitted={onSubmitted} />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
        active ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {children}
    </button>
  );
}

function InBrowserEditor({
  assignment,
  token,
  onSubmitted,
}: {
  assignment: CandidateAssignment;
  token: string;
  onSubmitted: (c: SubmissionConfirmation) => void;
}) {
  return assignment.file_type === "xlsx" ? (
    <XlsxEditor token={token} onSubmitted={onSubmitted} />
  ) : (
    <DocxEditor assignment={assignment} token={token} onSubmitted={onSubmitted} />
  );
}

function SubmitBar({
  message,
  submitting,
  onSubmit,
}: {
  message: string;
  submitting: boolean;
  onSubmit: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="text-sm text-slate-500">{message}</p>
      <button onClick={onSubmit} disabled={submitting} className="btn-primary">
        {submitting ? <Spinner className="h-4 w-4" /> : "Submit assessment"}
      </button>
    </div>
  );
}

function XlsxEditor({
  token,
  onSubmitted,
}: {
  token: string;
  onSubmitted: (c: SubmissionConfirmation) => void;
}) {
  const { notify } = useToast();
  const { data, loading, error } = useAsync(() => candidateApi.getWorkbook(token), [token]);
  const [change, setChange] = useState<GridChange>({ edits: {}, fieldValues: {} });
  const [submitting, setSubmitting] = useState(false);

  const fields = data?.fields ?? [];
  const missingRequired = useMemo(
    () =>
      fields
        .filter((f) => f.required)
        .filter((f) => String(change.fieldValues[f.id] ?? "").trim() === "")
        .map((f) => f.label),
    [fields, change],
  );

  const submit = async () => {
    if (missingRequired.length > 0) {
      notify("error", `Please complete: ${missingRequired.join(", ")}`);
      return;
    }
    setSubmitting(true);
    try {
      const c = await candidateApi.submitEdits(token, { cell_edits: change.edits });
      onSubmitted(c);
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingScreen label="Loading the spreadsheet…" />;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <SpreadsheetEditor view={data} onChange={setChange} />
      <SubmitBar
        submitting={submitting}
        onSubmit={submit}
        message={
          missingRequired.length === 0
            ? "All required cells are filled."
            : `${missingRequired.length} required cell(s) remaining.`
        }
      />
    </div>
  );
}

function DocxEditor({
  assignment,
  token,
  onSubmitted,
}: {
  assignment: CandidateAssignment;
  token: string;
  onSubmitted: (c: SubmissionConfirmation) => void;
}) {
  const { notify } = useToast();
  const { data, loading, error } = useAsync(() => candidateApi.getDocumentHtml(token), [token]);
  const [html, setHtml] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (data) setHtml(data.html);
  }, [data]);

  const requiredFields = (data?.fields ?? assignment.field_spec.fields).filter((f) => f.required);
  const missingRequired = useMemo(() => {
    return requiredFields
      .filter((f) => {
        const ph = (f.placeholder ?? f.id).replace(/[{}]/g, "").trim();
        return html.includes(`{{${ph}}}`) || html.includes(`{{ ${ph} }}`);
      })
      .map((f) => f.label);
  }, [requiredFields, html]);

  const submit = async () => {
    if (missingRequired.length > 0) {
      notify("error", `Please fill in the placeholders for: ${missingRequired.join(", ")}`);
      return;
    }
    setSubmitting(true);
    try {
      const c = await candidateApi.submitEdits(token, { document_html: html });
      onSubmitted(c);
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingScreen label="Loading the document…" />;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <RichTextEditor value={html} onChange={setHtml} ariaLabel="Document editor" minHeight="26rem" />
      <SubmitBar
        submitting={submitting}
        onSubmit={submit}
        message={
          missingRequired.length === 0
            ? "Ready to submit."
            : `${missingRequired.length} placeholder(s) still to fill.`
        }
      />
    </div>
  );
}

function UploadPanel({
  assignment,
  token,
  onSubmitted,
}: {
  assignment: CandidateAssignment;
  token: string;
  onSubmitted: (c: SubmissionConfirmation) => void;
}) {
  const { notify } = useToast();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const onSelect = async (file: File) => {
    setUploading(true);
    setProgress(0);
    try {
      const c = await candidateApi.submitUpload(token, file, setProgress);
      onSubmitted(c);
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card space-y-3 p-6">
      <p className="text-sm text-slate-600">
        Download the original template, edit it on your computer, then upload the completed
        <span className="font-medium"> .{assignment.file_type}</span> file. Macros are not allowed.
      </p>
      <FileDropzone
        accept={assignment.file_type === "xlsx" ? ".xlsx" : ".docx"}
        onSelect={onSelect}
        uploading={uploading}
        progress={progress}
      />
    </div>
  );
}

function ConfirmationView({ confirmation }: { confirmation: SubmissionConfirmation }) {
  const entries = Object.entries(confirmation.fields_submitted);
  return (
    <div className="card p-8 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h1 className="text-2xl font-bold text-slate-900">Submission received</h1>
      <p className="mt-2 text-slate-500">{confirmation.summary}</p>
      <div className="mt-4 flex items-center justify-center gap-2">
        <span className="text-sm text-slate-500">Automated status:</span>
        <ReviewBadge status={confirmation.review_status} />
      </div>

      {entries.length > 0 && (
        <div className="mx-auto mt-6 max-w-md text-left">
          <p className="mb-2 text-sm font-semibold text-slate-700">What you submitted</p>
          <dl className="divide-y divide-slate-100 rounded-xl border border-slate-200">
            {entries.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-4 py-2 text-sm">
                <dt className="text-slate-500">{k}</dt>
                <dd className="max-w-[60%] truncate font-medium text-slate-800">
                  {v === null || v === undefined || v === ""
                    ? "—"
                    : String(v).replace(/<[^>]+>/g, "")}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <p className="mt-6 text-xs text-slate-400">You can close this page now.</p>
    </div>
  );
}
