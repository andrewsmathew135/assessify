import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Spinner } from "../../components/ui";
import { RequestError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Sign in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="hidden flex-col justify-between bg-brand-600 p-12 text-white lg:flex">
        <div className="flex items-center gap-2 text-lg font-extrabold">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/20">A</span>
          Assessify
        </div>
        <div>
          <h1 className="text-4xl font-extrabold leading-tight">
            Streamline your candidate assessments.
          </h1>
          <p className="mt-4 max-w-md text-brand-100">
            Upload Word or Excel tasks, define what candidates must fill in, share a secure link,
            and let automated checks do the first pass of review.
          </p>
        </div>
        <p className="text-sm text-brand-200">Secure · Macro-free · Auditable</p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2 text-lg font-extrabold text-slate-900">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
                A
              </span>
              Assessify
            </div>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Access the assessment admin console.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            {error && <Alert kind="error">{error}</Alert>}
            <div>
              <label htmlFor="email" className="label">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="admin@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? <Spinner className="h-4 w-4" /> : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
