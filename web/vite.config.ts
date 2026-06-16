/// <reference types="vitest/config" />
// Vite build/dev configuration for the web client.
//
// Three responsibilities: (1) the React plugin compiles JSX/TSX; (2) the PWA
// plugin makes the app installable and caches the app *shell* for offline load
// (answers are deliberately never cached — they need a live, grounded API call);
// (3) the dev server proxies API paths to the FastAPI backend on :8000 so the
// frontend and API look same-origin in development, keeping auth and CORS simple.
// The `test` block configures Vitest (jsdom environment + the global setup file).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

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
