import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, EmptyState, LoadingScreen, ReviewBadge } from "../../components/ui";
import { adminApi } from "../../lib/api";
import { useAsync } from "../../lib/hooks";
import type { ReviewStatus } from "../../lib/types";

const FILTERS: { label: string; value: ReviewStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Needs review", value: "needs_review" },
  { label: "Passed", value: "passed" },
  { label: "Failed", value: "failed" },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<ReviewStatus | "all">("all");

  const { data, loading, error } = useAsync(
    () => adminApi.listSubmissions(filter === "all" ? {} : { status: filter }),
    [filter],
  );

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Submissions</h1>
          <p className="text-sm text-slate-500">Review candidate submissions and their automated checks.</p>
        </div>
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === f.value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingScreen label="Loading submissions…" />}
      {error && <Alert kind="error">{error}</Alert>}

      {!loading && !error && data && data.length === 0 && (
        <EmptyState
          title="No submissions yet"
          description="Once candidates submit their assessments, they’ll appear here."
        />
      )}

      {!loading && data && data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Candidate</th>
                <th className="px-4 py-3 font-semibold">Assessment</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Score</th>
                <th className="px-4 py-3 font-semibold">Source</th>
                <th className="px-4 py-3 font-semibold">Submitted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((row) => (
                <tr
                  key={row.submission_id}
                  onClick={() => navigate(`/submissions/${row.submission_id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-50"
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{row.candidate_name ?? "—"}</p>
                    {row.candidate_email && (
                      <p className="text-xs text-slate-400">{row.candidate_email}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.template_name}</td>
                  <td className="px-4 py-3">
                    <ReviewBadge status={row.review_status} />
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-700">
                    {row.score != null ? `${row.score}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {row.source === "in_browser" ? "In-browser" : "Upload"}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
