/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Dev proxy sends API calls to the FastAPI app (Phase 6). The technician PWA
// and the API are same-origin in production; in dev we proxy to :8000 so the
// dev-auth headers and CORS stay simple.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "FixMate",
        short_name: "FixMate",
        description: "AI troubleshooting assistant for field technicians",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        icons: [],
      },
      workbox: {
        // Shell caching only (plan §10): cache the app shell so the chat UI
        // loads offline. Answers themselves are never cached — groundedness and
        // freshness require a live API round-trip.
        globPatterns: ["**/*.{js,css,html,svg}"],
      },
    }),
  ],
  server: {
    proxy: {
      "/conversations": "http://localhost:8000",
      "/equipment": "http://localhost:8000",
      "/messages": "http://localhost:8000",
      "/documents": "http://localhost:8000",
      "/curation": "http://localhost:8000",
      "/fixes": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
