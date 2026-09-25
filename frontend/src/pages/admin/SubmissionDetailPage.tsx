import { Link, useParams } from "react-router-dom";
import { useToast } from "../../components/Toast";
import { Alert, LoadingScreen, ReviewBadge, Spinner } from "../../components/ui";
import { adminApi, RequestError, triggerBlobDownload } from "../../lib/api";
import { useAsync } from "../../lib/hooks";
import type { CheckResult, SubmissionDetail } from "../../lib/types";
import { useState } from "react";

export function SubmissionDetailPage() {
  const { id = "" } = useParams();
  const { data, loading, error, reload } = useAsync(() => adminApi.getSubmission(id), [id]);

  if (loading) return <LoadingScreen label="Loading submission…" />;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return null;
  return <Detail submission={data} onChange={reload} />;
}

function severityStyle(c: CheckResult): string {
  if (c.passed && c.severity !== "warning") return "text-emerald-600";
  if (c.severity === "warning") return "text-amber-600";
  return "text-red-600";
}

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "string") return v.replace(/<[^>]+>/g, "").trim() || "—";
  return String(v);
}

function Detail({ submission, onChange }: { submission: SubmissionDetail; onChange: () => void }) {
  const { notify } = useToast();
  const [rerunning, setRerunning] = useState(false);

  const download = async (which: "submitted" | "original") => {
    try {
      const blob = await adminApi.downloadSubmissionFile(submission.id, which);
      const name =
        which === "submitted"
          ? submission.submitted_filename
          : `original_${submission.template_name}.${submission.file_type}`;
      triggerBlobDownload(blob, name);
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Download failed.");
    }
  };

  const rerun = async () => {
    setRerunning(true);
    try {
      await adminApi.rerunReview(submission.id);
      notify("success", "Review re-run complete.");
      onChange();
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Re-run failed.");
    } finally {
      setRerunning(false);
    }
  };

  const report = submission.review_report;
  const diff = submission.diff_summary;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link to="/dashboard" className="hover:text-brand-600">
          Submissions
        </Link>
        <span>/</span>
        <span className="text-slate-700">{submission.candidate_name ?? "Submission"}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              {submission.candidate_name ?? "Candidate submission"}
            </h1>
            <ReviewBadge status={submission.review_status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {submission.template_name} ·{" "}
            {submission.source === "in_browser" ? "Edited in-browser" : "Uploaded file"} ·{" "}
            {new Date(submission.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => download("original")} className="btn-secondary">
            Original
          </button>
          <button onClick={() => download("submitted")} className="btn-secondary">
            Submitted
          </button>
          <button onClick={rerun} disabled={rerunning} className="btn-primary">
            {rerunning ? <Spinner className="h-4 w-4" /> : "Re-run review"}
          </button>
        </div>
      </div>

      {report && (
        <section className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">Automated review</h2>
            {submission.score != null && (
              <span className="text-sm font-semibold text-slate-600">Score: {submission.score}%</span>
            )}
          </div>
          <p className="mb-4 text-sm text-slate-600">{report.summary}</p>
          <div className="mb-4 flex gap-4 text-sm">
            <span className="text-emerald-600">✓ {report.passed_count} passed</span>
            <span className="text-red-600">✕ {report.failed_count} failed</span>
            <span className="text-amber-600">! {report.warning_count} warnings</span>
          </div>
          <ul className="space-y-2">
            {report.checks.map((c) => (
              <li key={c.id} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 font-bold ${severityStyle(c)}`}>
                  {c.passed && c.severity !== "warning" ? "✓" : c.severity === "warning" ? "!" : "✕"}
                </span>
                <span className="text-slate-600">{c.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {diff && diff.fields.length > 0 && (
        <section className="card overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-slate-800">Changes vs template</h2>
            <p className="text-sm text-slate-500">{diff.changed_count} field(s) changed.</p>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-6 py-3 font-semibold">Field</th>
                <th className="px-6 py-3 font-semibold">Original</th>
                <th className="px-6 py-3 font-semibold">Submitted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {diff.fields.map((d) => (
                <tr key={d.field_id} className={d.changed ? "bg-amber-50/40" : ""}>
                  <td className="px-6 py-3 font-medium text-slate-700">{d.label}</td>
                  <td className="px-6 py-3 text-slate-400">{fmt(d.original)}</td>
                  <td className="px-6 py-3 font-medium text-slate-800">{fmt(d.submitted)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
