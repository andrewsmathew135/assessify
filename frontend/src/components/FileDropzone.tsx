import { useRef, useState, type DragEvent } from "react";
import { Spinner } from "./ui";

interface FileDropzoneProps {
  accept: ".docx" | ".xlsx";
  onSelect: (file: File) => void;
  uploading?: boolean;
  progress?: number;
  maxBytes?: number;
}

export function FileDropzone({
  accept,
  onSelect,
  uploading = false,
  progress = 0,
  maxBytes = 10 * 1024 * 1024,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const validateAndSelect = (file: File) => {
    setError(null);
    const lower = file.name.toLowerCase();
    if (!lower.endsWith(accept)) {
      setError(`Please choose a ${accept} file.`);
      return;
    }
    if (file.size > maxBytes) {
      setError(`File is too large (max ${(maxBytes / 1024 / 1024).toFixed(0)} MB).`);
      return;
    }
    setFileName(file.name);
    onSelect(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) validateAndSelect(file);
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        role="button"
        tabIndex={0}
        aria-label={`Upload a ${accept} file`}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50 hover:bg-slate-100"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) validateAndSelect(file);
          }}
        />
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-600">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L8 8m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">
            {fileName ?? <>Drag &amp; drop or <span className="text-brand-600">browse</span></>}
          </p>
          <p className="mt-1 text-xs text-slate-500">Accepted: {accept} · max {(maxBytes / 1024 / 1024).toFixed(0)} MB · no macros</p>
        </div>
      </div>

      {uploading && (
        <div className="mt-3">
          <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-500">
            <span className="flex items-center gap-1.5">
              <Spinner className="h-3.5 w-3.5 text-brand-600" /> Uploading…
            </span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-brand-600 transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-sm font-medium text-red-600">{error}</p>}
    </div>
  );
}
