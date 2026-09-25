import type {
  CandidateAssignment,
  DashboardRow,
  DocumentHtml,
  DocumentView,
  ReviewStatus,
  SessionLink,
  SubmissionConfirmation,
  SubmissionDetail,
  SubmitEditsBody,
  Template,
  TemplateListItem,
  FieldSpec,
  WorkbookView,
  ApiError,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const TOKEN_KEY = "assess_admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class RequestError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown> | null;
  constructor(status: number, error: ApiError) {
    super(error.message);
    this.code = error.code;
    this.status = status;
    this.details = error.details;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false } = opts;
  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/api${path}`, { method, headers, body: payload });
  } catch {
    throw new RequestError(0, {
      code: "network_error",
      message: "Could not reach the server. Please check your connection and try again.",
    });
  }

  if (resp.status === 204) return undefined as T;

  const contentType = resp.headers.get("content-type") ?? "";
  if (!resp.ok) {
    let err: ApiError = { code: "error", message: `Request failed (${resp.status}).` };
    if (contentType.includes("application/json")) {
      const data = await resp.json().catch(() => null);
      if (data && typeof data.message === "string") err = data as ApiError;
    }
    if (resp.status === 401 && auth) setToken(null);
    throw new RequestError(resp.status, err);
  }

  if (contentType.includes("application/json")) return (await resp.json()) as T;
  return (await resp.blob()) as unknown as T;
}

async function download(path: string, auth = false): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const resp = await fetch(`${API_BASE}/api${path}`, { headers });
  if (!resp.ok) throw new RequestError(resp.status, { code: "error", message: "Download failed." });
  return resp.blob();
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

interface UploadOptions {
  fields?: Record<string, string>;
  auth?: boolean;
  onProgress?: (percent: number) => void;
}

// XHR-based upload so we can report real byte-level progress to the UI.
export function uploadFile<T>(path: string, file: File, opts: UploadOptions = {}): Promise<T> {
  const { fields = {}, auth = false, onProgress } = opts;
  return new Promise<T>((resolve, reject) => {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    fd.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api${path}`);
    if (auth) {
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T);
      } else {
        const err = (data as ApiError) ?? { code: "error", message: "Upload failed." };
        if (xhr.status === 401 && auth) setToken(null);
        reject(new RequestError(xhr.status, err));
      }
    };
    xhr.onerror = () =>
      reject(
        new RequestError(0, {
          code: "network_error",
          message: "Could not reach the server during upload.",
        }),
      );
    xhr.send(fd);
  });
}

// --------------------------------------------------------------------------- //
// Public config
// --------------------------------------------------------------------------- //
export const configApi = {
  get: () => request<{ app_name: string; auth_enabled: boolean }>("/config"),
};

// --------------------------------------------------------------------------- //
// Auth
// --------------------------------------------------------------------------- //
export const authApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string; expires_in_minutes: number }>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  me: () => request<{ email: string; role: string }>("/auth/me", { auth: true }),
};

// --------------------------------------------------------------------------- //
// Admin
// --------------------------------------------------------------------------- //
export const adminApi = {
  listTemplates: () => request<TemplateListItem[]>("/admin/templates", { auth: true }),
  getTemplate: (id: string) => request<Template>(`/admin/templates/${id}`, { auth: true }),
  uploadTemplate: (name: string, instructions: string, file: File, onProgress?: (p: number) => void) =>
    uploadFile<Template>("/admin/templates", file, {
      fields: { name, instructions },
      auth: true,
      onProgress,
    }),
  updateTemplate: (id: string, patch: { name?: string; instructions?: string; field_spec?: FieldSpec }) =>
    request<Template>(`/admin/templates/${id}`, { method: "PATCH", body: patch, auth: true }),
  deleteTemplate: (id: string) =>
    request<{ message: string }>(`/admin/templates/${id}`, { method: "DELETE", auth: true }),
  downloadTemplateOriginal: (id: string) => download(`/admin/templates/${id}/original`, true),

  createSession: (template_id: string, candidate_name?: string, candidate_email?: string) =>
    request<SessionLink>("/admin/sessions", {
      method: "POST",
      body: { template_id, candidate_name, candidate_email },
      auth: true,
    }),
  listSessions: (template_id?: string) =>
    request<SessionLink[]>(
      `/admin/sessions${template_id ? `?template_id=${encodeURIComponent(template_id)}` : ""}`,
      { auth: true },
    ),

  listSubmissions: (filters: { status?: ReviewStatus; template_id?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.template_id) params.set("template_id", filters.template_id);
    const qs = params.toString();
    return request<DashboardRow[]>(`/admin/submissions${qs ? `?${qs}` : ""}`, { auth: true });
  },
  getSubmission: (id: string) =>
    request<SubmissionDetail>(`/admin/submissions/${id}`, { auth: true }),
  rerunReview: (id: string) =>
    request<SubmissionDetail>(`/admin/submissions/${id}/review`, { method: "POST", auth: true }),
  downloadSubmissionFile: (id: string, which: "submitted" | "original") =>
    download(`/admin/submissions/${id}/file?which=${which}`, true),
};

// --------------------------------------------------------------------------- //
// Candidate
// --------------------------------------------------------------------------- //
export const candidateApi = {
  openAssignment: (token: string) =>
    request<CandidateAssignment>(`/candidate/${token}`),
  getWorkbook: (token: string) => request<WorkbookView>(`/candidate/${token}/workbook`),
  getDocument: (token: string) => request<DocumentView>(`/candidate/${token}/document`),
  getDocumentHtml: (token: string) =>
    request<DocumentHtml>(`/candidate/${token}/document-html`),
  submitEdits: (token: string, body: SubmitEditsBody) =>
    request<SubmissionConfirmation>(`/candidate/${token}/submit-edits`, {
      method: "POST",
      body,
    }),
  submitUpload: (token: string, file: File, onProgress?: (p: number) => void) =>
    uploadFile<SubmissionConfirmation>(`/candidate/${token}/submit-upload`, file, { onProgress }),
};
