/// <reference types="vitest/config" />
// Vite build/dev configuration for the web client.
//
// Three responsibilities: (1) the React plugin compiles JSX/TSX; (2) the PWA
// plugin makes the app installable and caches the app *shell* for offline load
// (answers are deliberately never cached — they need a live, grounded API call);
// (3) the dev server proxies API paths to the FastAPI backend on :8000 so the
// frontend and API look same-origin in development, keeping auth and CORS simple.
// The `test` block configures Vitest (jsdom environment + the global setup file).
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Build version string, injected as the `__APP_VERSION__` global (see
// src/version.d.ts) and shown in the GUI. The patch number is the git commit
// count, so it auto-increments on every commit with no manual bump — the
// major.minor base still comes from package.json. The short commit hash is
// appended for traceability back to an exact build. Both git lookups fall back
// gracefully (e.g. building outside a git checkout) so the build never fails.
function buildVersion(): string {
  const base = JSON.parse(readFileSync("./package.json", "utf-8")).version as string;
  const [major = "0", minor = "0"] = base.split(".");
  const git = (cmd: string, fallback: string) => {
    try {
      return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    } catch {
      return fallback;
    }
  };
  const commits = git("git rev-list --count HEAD", "0");
  const hash = git("git rev-parse --short HEAD", "nogit");
  return `${major}.${minor}.${commits}+${hash}`;
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(buildVersion()),
  },
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
