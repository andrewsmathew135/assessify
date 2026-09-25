import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-4 text-center">
      <p className="text-6xl font-extrabold text-brand-600">404</p>
      <h1 className="text-xl font-semibold text-slate-800">Page not found</h1>
      <p className="max-w-sm text-slate-500">
        The page you’re looking for doesn’t exist or the link may be incorrect.
      </p>
      <Link to="/dashboard" className="btn-primary">
        Go to dashboard
      </Link>
    </div>
  );
}
