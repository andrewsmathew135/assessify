import { useState, type FormEvent, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FileDropzone } from "../../components/FileDropzone";
import { useToast } from "../../components/Toast";
import { Alert, EmptyState, FileTypeIcon, LoadingScreen } from "../../components/ui";
import { adminApi, RequestError } from "../../lib/api";
import { useAsync } from "../../lib/hooks";

export function TemplatesPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const { data, loading, error, reload } = useAsync(() => adminApi.listTemplates(), []);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [formError, setFormError] = useState<string | null>(null);

  const reset = () => {
    setCreating(false);
    setName("");
    setInstructions("");
    setFile(null);
    setProgress(0);
    setFormError(null);
  };

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!file) {
      setFormError("Please choose a .docx or .xlsx file.");
      return;
    }
    setUploading(true);
    try {
      const tpl = await adminApi.uploadTemplate(name, instructions, file, setProgress);
      notify("success", "Template uploaded. Now define the required fields.");
      reset();
      navigate(`/templates/${tpl.id}`);
    } catch (err) {
      setFormError(err instanceof RequestError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async (id: string, e: MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this template and all its links and submissions? This cannot be undone."))
      return;
    try {
      await adminApi.deleteTemplate(id);
      notify("success", "Template deleted.");
      reload();
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Delete failed.");
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Templates</h1>
          <p className="text-sm text-slate-500">Upload assessment files and define what candidates must fill in.</p>
        </div>
        {!creating && (
          <button onClick={() => setCreating(true)} className="btn-primary">
            + New template
          </button>
        )}
      </div>

      {creating && (
        <form onSubmit={onCreate} className="card mb-6 space-y-4 p-6">
          <h2 className="text-lg font-semibold text-slate-800">New template</h2>
          {formError && <Alert kind="error">{formError}</Alert>}
          <div>
            <label htmlFor="tname" className="label">
              Name
            </label>
            <input
              id="tname"
              className="input"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Data Analyst Take-home"
            />
          </div>
          <div>
            <label htmlFor="tinstr" className="label">
              Instructions for candidates
            </label>
            <textarea
              id="tinstr"
              className="input min-h-[80px]"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Explain the task clearly…"
            />
          </div>
          <div>
            <span className="label">Assessment file (.docx or .xlsx)</span>
            <FileDropzone
              accept={name.toLowerCase().includes("xls") ? ".xlsx" : ".docx"}
              onSelect={setFile}
              uploading={uploading}
              progress={progress}
            />
            <p className="mt-2 text-xs text-slate-500">
              Tip: both .docx and .xlsx are accepted — the dropzone hint updates, but you can drop either type.
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={reset} className="btn-secondary" disabled={uploading}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={uploading}>
              {uploading ? "Uploading…" : "Upload & continue"}
            </button>
          </div>
        </form>
      )}

      {loading && <LoadingScreen label="Loading templates…" />}
      {error && <Alert kind="error">{error}</Alert>}

      {!loading && data && data.length === 0 && !creating && (
        <EmptyState
          title="No templates yet"
          description="Upload a Word or Excel file to create your first assessment template."
          action={
            <button onClick={() => setCreating(true)} className="btn-primary">
              Upload a template
            </button>
          }
        />
      )}

      {!loading && data && data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((t) => (
            <button
              key={t.id}
              onClick={() => navigate(`/templates/${t.id}`)}
              className="card group flex flex-col items-start gap-3 p-5 text-left transition-shadow hover:shadow-md"
            >
              <div className="flex w-full items-start justify-between">
                <FileTypeIcon type={t.file_type} />
                <span
                  onClick={(e) => onDelete(t.id, e)}
                  className="rounded-md p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"
                  aria-label="Delete template"
                  role="button"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </span>
              </div>
              <div>
                <p className="font-semibold text-slate-800 group-hover:text-brand-700">{t.name}</p>
                <p className="mt-0.5 truncate text-xs text-slate-400">{t.original_filename}</p>
              </div>
              <p className="mt-auto text-xs text-slate-400">
                {new Date(t.created_at).toLocaleDateString()}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
