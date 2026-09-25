import type { DocBlock, FieldDefinition } from "../lib/types";
import { RichTextEditor } from "./RichTextEditor";

interface DocumentEditorProps {
  blocks: DocBlock[];
  fields: FieldDefinition[];
  values: Record<string, string>;
  onChange: (fieldId: string, value: string) => void;
}

export function DocumentEditor({ blocks, fields, values, onChange }: DocumentEditorProps) {
  const fieldMap = new Map(fields.map((f) => [f.id, f]));

  return (
    <div className="card space-y-1 px-6 py-6 leading-relaxed text-slate-800">
      {blocks.map((block, i) => {
        const isHeading = (block.style ?? "").toLowerCase().includes("heading");
        return (
          <div key={i} className={isHeading ? "pt-2 text-lg font-semibold text-slate-900" : ""}>
            {block.runs.length === 0 ? (
              <span>&nbsp;</span>
            ) : (
              block.runs.map((run, j) => {
                if ("text" in run) return <span key={j}>{run.text}</span>;
                const field = fieldMap.get(run.field);
                if (!field) return <span key={j} className="text-red-500">[{run.field}]</span>;
                return (
                  <InlineField
                    key={j}
                    field={field}
                    value={values[field.id] ?? ""}
                    onChange={(v) => onChange(field.id, v)}
                  />
                );
              })
            )}
          </div>
        );
      })}
    </div>
  );
}

function InlineField({
  field,
  value,
  onChange,
}: {
  field: FieldDefinition;
  value: string;
  onChange: (v: string) => void;
}) {
  if (field.rich_text) {
    return (
      <div className="my-3 rounded-xl border border-brand-200 bg-brand-50/40 p-3">
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-brand-700">
          {field.label}
          {field.required && <span className="text-red-500"> *</span>}
        </label>
        {field.help_text && <p className="mb-2 text-xs text-slate-500">{field.help_text}</p>}
        <RichTextEditor value={value} onChange={onChange} ariaLabel={field.label} />
      </div>
    );
  }

  return (
    <input
      type={field.type === "number" || field.type === "integer" ? "number" : "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={field.label}
      placeholder={field.label}
      required={field.required}
      className="mx-1 inline-block min-w-[8rem] rounded-md border-b-2 border-brand-400 bg-brand-50 px-2 py-0.5 text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-0"
    />
  );
}
