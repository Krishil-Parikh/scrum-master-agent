import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// AI Dev Pod frontend. Talks to the FastAPI backend (default
// http://localhost:8000) via REST + a WebSocket -- see src/api/client.ts.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  resolve: {
    alias: {
      "@": "/src",
    },
  },
});
