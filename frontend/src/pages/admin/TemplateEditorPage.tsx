import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useToast } from "../../components/Toast";
import { Alert, FileTypeIcon, LoadingScreen, SessionBadge, Spinner } from "../../components/ui";
import { adminApi, RequestError, triggerBlobDownload } from "../../lib/api";
import { useAsync } from "../../lib/hooks";
import type { FieldDefinition, FieldValueType, Template } from "../../lib/types";

const TYPES: FieldValueType[] = ["string", "number", "integer", "boolean", "date"];

function blankField(fileType: "docx" | "xlsx", index: number): FieldDefinition {
  const id = `field_${index + 1}`;
  return {
    id,
    label: `Field ${index + 1}`,
    type: "string",
    required: true,
    rich_text: false,
    sheet: fileType === "xlsx" ? "Sheet1" : null,
    cell: fileType === "xlsx" ? "" : null,
    placeholder: fileType === "docx" ? `{{${id}}}` : null,
    help_text: null,
    min: null,
    max: null,
    min_length: null,
    max_length: null,
    pattern: null,
    allowed_values: null,
  };
}

export function TemplateEditorPage() {
  const { id = "" } = useParams();
  const { data, loading, error, reload } = useAsync(() => adminApi.getTemplate(id), [id]);

  if (loading) return <LoadingScreen label="Loading template…" />;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return null;
  return <Editor template={data} onSaved={reload} />;
}

function Editor({ template, onSaved }: { template: Template; onSaved: () => void }) {
  const { notify } = useToast();
  const [name, setName] = useState(template.name);
  const [instructions, setInstructions] = useState(template.instructions);
  const [fields, setFields] = useState<FieldDefinition[]>(template.field_spec.fields);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(template.name);
    setInstructions(template.instructions);
    setFields(template.field_spec.fields);
  }, [template]);

  const update = (i: number, patch: Partial<FieldDefinition>) =>
    setFields((fs) => fs.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  const remove = (i: number) => setFields((fs) => fs.filter((_, idx) => idx !== i));
  const add = () => setFields((fs) => [...fs, blankField(template.file_type, fs.length)]);

  const save = async () => {
    // Client-side guard mirroring backend rules.
    for (const f of fields) {
      if (template.file_type === "xlsx" && (!f.sheet || !f.cell)) {
        notify("error", `Field "${f.label}" needs a sheet and cell.`);
        return;
      }
      if (template.file_type === "docx" && !f.placeholder) {
        notify("error", `Field "${f.label}" needs a placeholder.`);
        return;
      }
    }
    setSaving(true);
    try {
      await adminApi.updateTemplate(template.id, { name, instructions, field_spec: { fields } });
      notify("success", "Template saved.");
      onSaved();
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const downloadOriginal = async () => {
    const blob = await adminApi.downloadTemplateOriginal(template.id).catch(() => null);
    if (blob) triggerBlobDownload(blob, template.original_filename);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link to="/templates" className="hover:text-brand-600">
          Templates
        </Link>
        <span>/</span>
        <span className="text-slate-700">{template.name}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <FileTypeIcon type={template.file_type} />
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Configure assessment</h1>
            <p className="text-sm text-slate-500">{template.original_filename}</p>
          </div>
        </div>
        <button onClick={save} disabled={saving} className="btn-primary">
          {saving ? <Spinner className="h-4 w-4" /> : "Save changes"}
        </button>
      </div>

      {/* Details */}
      <section className="card space-y-4 p-6">
        <h2 className="text-lg font-semibold text-slate-800">Details</h2>
        <div>
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Instructions for candidates</label>
          <textarea
            className="input min-h-[90px]"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
        </div>
      </section>

      {/* Fields */}
      <section className="card p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Required fields</h2>
            <p className="text-sm text-slate-500">
              {template.file_type === "xlsx"
                ? "Map each field to a sheet + cell candidates must fill (e.g. Sheet1 / B2)."
                : "Map each field to a placeholder in the document (e.g. {{full_name}})."}
            </p>
          </div>
          <button onClick={add} className="btn-secondary">
            + Add field
          </button>
        </div>

        {fields.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            No fields yet. Add the first field candidates must complete.
          </p>
        ) : (
          <div className="space-y-4">
            {fields.map((f, i) => (
              <FieldEditor
                key={i}
                field={f}
                fileType={template.file_type}
                onChange={(patch) => update(i, patch)}
                onRemove={() => remove(i)}
              />
            ))}
          </div>
        )}
      </section>

      <SessionsSection templateId={template.id} />

      <button onClick={downloadOriginal} className="btn-ghost text-sm">
        ↓ Download original template file
      </button>
    </div>
  );
}

function FieldEditor({
  field,
  fileType,
  onChange,
  onRemove,
}: {
  field: FieldDefinition;
  fileType: "docx" | "xlsx";
  onChange: (patch: Partial<FieldDefinition>) => void;
  onRemove: () => void;
}) {
  const isNumeric = field.type === "number" || field.type === "integer";
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="label">Field ID</label>
          <input
            className="input"
            value={field.id}
            onChange={(e) => onChange({ id: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Label</label>
          <input
            className="input"
            value={field.label}
            onChange={(e) => onChange({ label: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Type</label>
          <select
            className="input"
            value={field.type}
            onChange={(e) => onChange({ type: e.target.value as FieldValueType })}
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        {fileType === "xlsx" ? (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label">Sheet</label>
              <input
                className="input"
                value={field.sheet ?? ""}
                onChange={(e) => onChange({ sheet: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Cell</label>
              <input
                className="input"
                placeholder="B2"
                value={field.cell ?? ""}
                onChange={(e) => onChange({ cell: e.target.value.toUpperCase() })}
              />
            </div>
          </div>
        ) : (
          <div>
            <label className="label">Placeholder</label>
            <input
              className="input"
              placeholder="{{full_name}}"
              value={field.placeholder ?? ""}
              onChange={(e) => onChange({ placeholder: e.target.value })}
            />
          </div>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {isNumeric && (
          <>
            <div>
              <label className="label">Min</label>
              <input
                type="number"
                className="input"
                value={field.min ?? ""}
                onChange={(e) => onChange({ min: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label">Max</label>
              <input
                type="number"
                className="input"
                value={field.max ?? ""}
                onChange={(e) => onChange({ max: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </div>
          </>
        )}
        {!isNumeric && (
          <>
            <div>
              <label className="label">Min length</label>
              <input
                type="number"
                className="input"
                value={field.min_length ?? ""}
                onChange={(e) =>
                  onChange({ min_length: e.target.value === "" ? null : Number(e.target.value) })
                }
              />
            </div>
            <div>
              <label className="label">Pattern (regex)</label>
              <input
                className="input"
                value={field.pattern ?? ""}
                onChange={(e) => onChange({ pattern: e.target.value || null })}
              />
            </div>
          </>
        )}
        <div>
          <label className="label">Help text</label>
          <input
            className="input"
            value={field.help_text ?? ""}
            onChange={(e) => onChange({ help_text: e.target.value || null })}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={field.required}
            onChange={(e) => onChange({ required: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Required
        </label>
        {fileType === "docx" && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={field.rich_text}
              onChange={(e) => onChange({ rich_text: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Rich text (bold/italic/lists)
          </label>
        )}
        <button onClick={onRemove} className="ml-auto text-sm font-medium text-red-500 hover:text-red-600">
          Remove
        </button>
      </div>
    </div>
  );
}

function SessionsSection({ templateId }: { templateId: string }) {
  const { notify } = useToast();
  const { data, loading, reload } = useAsync(() => adminApi.listSessions(templateId), [templateId]);
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [creating, setCreating] = useState(false);

  const candidateUrl = (token: string, given?: string | null) => {
    if (given && /^https?:\/\//.test(given)) return given;
    return `${window.location.origin}/c/${token}`;
  };

  const createLink = async () => {
    setCreating(true);
    try {
      const s = await adminApi.createSession(templateId, candidateName || undefined, candidateEmail || undefined);
      await navigator.clipboard.writeText(candidateUrl(s.token, s.candidate_url)).catch(() => {});
      notify("success", "Link created and copied to clipboard.");
      setCandidateName("");
      setCandidateEmail("");
      reload();
    } catch (err) {
      notify("error", err instanceof RequestError ? err.message : "Could not create link.");
    } finally {
      setCreating(false);
    }
  };

  const copy = async (token: string, url?: string | null) => {
    await navigator.clipboard.writeText(candidateUrl(token, url)).catch(() => {});
    notify("success", "Link copied.");
  };

  return (
    <section className="card p-6">
      <h2 className="text-lg font-semibold text-slate-800">Candidate links</h2>
      <p className="mb-4 text-sm text-slate-500">
        Generate a unique, unguessable link per candidate. Anyone with the link can complete the assessment.
      </p>

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[10rem]">
          <label className="label">Candidate name (optional)</label>
          <input className="input" value={candidateName} onChange={(e) => setCandidateName(e.target.value)} />
        </div>
        <div className="flex-1 min-w-[10rem]">
          <label className="label">Email (optional)</label>
          <input
            type="email"
            className="input"
            value={candidateEmail}
            onChange={(e) => setCandidateEmail(e.target.value)}
          />
        </div>
        <button onClick={createLink} disabled={creating} className="btn-primary">
          {creating ? <Spinner className="h-4 w-4" /> : "Generate link"}
        </button>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-brand-600" />
      ) : data && data.length > 0 ? (
        <div className="divide-y divide-slate-100">
          {data.map((s) => (
            <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="font-medium text-slate-700">{s.candidate_name ?? "Unnamed candidate"}</p>
                <p className="truncate text-xs text-slate-400">{candidateUrl(s.token, s.candidate_url)}</p>
              </div>
              <div className="flex items-center gap-3">
                <SessionBadge status={s.status} />
                <button onClick={() => copy(s.token, s.candidate_url)} className="btn-secondary py-1.5 text-xs">
                  Copy link
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-500">No links generated yet.</p>
      )}
    </section>
  );
}
