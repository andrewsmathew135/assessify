import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { AdminLayout } from "./components/AdminLayout";
import { LoadingScreen } from "./components/ui";
import { useAuth } from "./lib/auth";
import { DashboardPage } from "./pages/admin/DashboardPage";
import { LoginPage } from "./pages/admin/LoginPage";
import { SubmissionDetailPage } from "./pages/admin/SubmissionDetailPage";
import { TemplateEditorPage } from "./pages/admin/TemplateEditorPage";
import { TemplatesPage } from "./pages/admin/TemplatesPage";
import { AssignmentPage } from "./pages/candidate/AssignmentPage";
import { NotFoundPage } from "./pages/NotFoundPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingScreen label="Loading…" />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LoginRoute() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingScreen label="Loading…" />;
  // When auth is disabled (or already signed in), skip the login screen.
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <LoginPage />;
}

export default function App() {
  return (
    <Routes>
      {/* Public candidate route */}
      <Route path="/c/:token" element={<AssignmentPage />} />

      {/* Admin auth */}
      <Route path="/login" element={<LoginRoute />} />

      {/* Admin app (protected) */}
      <Route
        element={
          <RequireAuth>
            <AdminLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/templates/:id" element={<TemplateEditorPage />} />
        <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
