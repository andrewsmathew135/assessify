import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function AdminLayout() {
  const { email, authEnabled, logout } = useAuth();
  const navigate = useNavigate();

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
      isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <button
              onClick={() => navigate("/dashboard")}
              className="flex items-center gap-2 font-extrabold tracking-tight text-slate-900"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
                A
              </span>
              Assessify
            </button>
            <nav className="hidden items-center gap-1 sm:flex">
              <NavLink to="/dashboard" className={navClass}>
                Dashboard
              </NavLink>
              <NavLink to="/templates" className={navClass}>
                Templates
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {authEnabled ? (
              <>
                <span className="hidden text-sm text-slate-500 sm:inline">{email}</span>
                <button onClick={logout} className="btn-secondary py-2">
                  Sign out
                </button>
              </>
            ) : (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                Open mode
              </span>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
