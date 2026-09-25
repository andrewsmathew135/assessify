import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development, proxy API calls to the FastAPI backend so the frontend can
// call same-origin "/api/*" without CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_API_TARGET || "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
