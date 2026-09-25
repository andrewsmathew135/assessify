/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API, e.g. https://api.example.com. Empty in dev (proxied). */
  readonly VITE_API_BASE_URL?: string;
  /** Dev-only proxy target for /api. */
  readonly VITE_DEV_API_TARGET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
