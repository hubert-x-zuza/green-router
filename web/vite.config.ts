import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs on :8000 (make api); in Docker nginx proxies /api.
// maplibre-gl 6 loads its web worker by a URL relative to its own module: pre-bundling breaks
// that path, so the package is served as is.
export default defineConfig({
  plugins: [react()],
  optimizeDeps: { exclude: ["maplibre-gl"] },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  preview: { port: 4173, proxy: { "/api": "http://localhost:8000" } },
});
