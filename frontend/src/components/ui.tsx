import type { ReactNode } from "react";
import type { ReviewStatus, SessionStatus } from "../lib/types";

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

export function LoadingScreen({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-slate-500">
      <Spinner className="h-8 w-8 text-brand-600" />
      <p className="text-sm font-medium">{label}</p>
    </div>
  );
}

const REVIEW_STYLES: Record<ReviewStatus, { label: string; cls: string }> = {
  passed: { label: "Passed", cls: "bg-emerald-100 text-emerald-800" },
  failed: { label: "Failed", cls: "bg-red-100 text-red-800" },
  needs_review: { label: "Needs review", cls: "bg-amber-100 text-amber-800" },
  pending: { label: "Pending", cls: "bg-slate-100 text-slate-700" },
};

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  const s = REVIEW_STYLES[status];
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

const SESSION_STYLES: Record<SessionStatus, { label: string; cls: string }> = {
  pending: { label: "Not opened", cls: "bg-slate-100 text-slate-700" },
  opened: { label: "Opened", cls: "bg-brand-100 text-brand-800" },
  submitted: { label: "Submitted", cls: "bg-emerald-100 text-emerald-800" },
  expired: { label: "Expired", cls: "bg-red-100 text-red-800" },
};

export function SessionBadge({ status }: { status: SessionStatus }) {
  const s = SESSION_STYLES[status];
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

export function Alert({
  kind = "error",
  children,
}: {
  kind?: "error" | "info" | "warning" | "success";
  children: ReactNode;
}) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    info: "border-brand-200 bg-brand-50 text-brand-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[kind];
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${styles}`} role="alert">
      {children}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div>
        <p className="font-semibold text-slate-800">{title}</p>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function FileTypeIcon({ type }: { type: "docx" | "xlsx" }) {
  const color = type === "docx" ? "text-blue-600" : "text-emerald-600";
  return (
    <span
      className={`inline-flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold ${color}`}
      title={type.toUpperCase()}
    >
      {type === "docx" ? "DOC" : "XLS"}
    </span>
  );
}
